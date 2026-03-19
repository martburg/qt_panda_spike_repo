# src/steuerung3d/apps/yellow/controllers/hip_controller.py
"""HiP (operator-side HMI) controller.

Orchestration only:
- read telemetry
- read UI inputs
- call HipEngine
- publish intents
- apply HipViewModel
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar, cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from steuerung3d.apps.hi_p.smoke_control import UdpHiPSmokeControlIn
from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat
from steuerung3d.util.ratelimit import rl_log_exc

from ..binders.hip_qt_binder import HipQtBinder
from ..engines.hip.engine import HipEngine, HipParamAction, HipUiInputs
from ..engines.hip.viewmodel import HipViewModel
from ..ports import IntentOut, TelemetryIn
from ..qtutil.bindings import YellowBindings
from ..qtutil.perf_watchdog import PerfWatchdog
from ..runtimes.hip_runtime import HipRuntime, HipRuntimeResult
from .controller_utils import (
    GuardedControllerOps,
    StatusEmitterLike,
    best_effort,
    init_observability,
    run_guarded,
    start_poll_timer,
)

_StatusEmitterCls: type[object] | None

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter as _StatusEmitter  # type: ignore

    _StatusEmitterCls = _StatusEmitter
except Exception:  # pragma: no cover
    _StatusEmitterCls = None


log = logging.getLogger("hi_p")

_T = TypeVar("_T")


def _new_soft_error_counts() -> dict[str, int]:
    return {}


@dataclass
class HiPController:
    win: QWidget
    intent_out: IntentOut
    telemetry_in: TelemetryIn

    shadow_mode: str | None = None
    hip_id: str = ""

    # If we stop receiving telemetry for this long, we go back to UNKNOWN
    stale_after_ms: int = 500

    _dbg_next_s: float = 0.0
    _dbg_vm_keys_once: bool = False
    _ui_log_next_s: float = 0.0
    _last_ui_log_key: tuple[object, ...] | None = None

    # Binder apply throttling (avoid log spam on repeated UI update errors)
    _binder_apply_err_last_s: float = 0.0

    # Late-initialized internal members (kept out of __init__ signature)
    ui: YellowBindings = field(init=False)

    _hb: Heartbeat = field(init=False)
    _ch: ChangeTracker = field(init=False)
    _status: StatusEmitterLike | None = field(init=False, default=None)
    _timer: QTimer | None = field(init=False, default=None)

    # Qt-free runtime/engine
    _hip_engine: HipEngine = field(init=False)
    _hip_runtime: HipRuntime = field(init=False)
    _binder: HipQtBinder = field(init=False)
    _soft_errors: dict[str, int] = field(init=False, default_factory=_new_soft_error_counts)
    _wd: PerfWatchdog = field(init=False)
    _fixed_axis: str = field(init=False, default="")
    _lock_axis_combo: bool = field(init=False, default=False)
    _last_mode: str = field(init=False, default="")
    _last_estop: bool = field(init=False, default=False)
    _last_fault: bool = field(init=False, default=False)
    _last_estate: str = field(init=False, default="ESTOP")
    _hip_id: str = field(init=False, default="")
    _smoke_control_in: UdpHiPSmokeControlIn | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.ui = YellowBindings.from_window(self.win)

        # Soft-error counters for swallowed exceptions (binder/UI)
        self._soft_errors = _new_soft_error_counts()
        self._guard_ops = GuardedControllerOps(self._soft_errors)

        # --- Qt binder (UI-only) ---
        self._binder = HipQtBinder(self.win, log)

        # --- Observability (logging + optional supervisor heartbeat) ---
        self._init_observability()
        self._wd = PerfWatchdog(log, name="hi_p")

        # --- HiP runtime (Qt-free orchestration)
        self._hip_engine = HipEngine(hip_id=self._hip_id)
        self._hip_runtime = HipRuntime(
            engine=self._hip_engine,
            hb=self._hb,
            ch=self._ch,
            status=self._status,
            stale_after_ms=self.stale_after_ms,
            log=log,
            hip_id=self._hip_id,
            shadow_mode=self.shadow_mode,
        )

        # self._timer is declared as a dataclass field for typing; value set here.
        self._timer = None

        # Axis selection config (pooling/fixed-axis)
        self._fixed_axis: str = ""
        self._lock_axis_combo: bool = False

        # Paint an explicit startup state (unknown dots, no tick, etc.)
        self._best_effort("binder.apply_startup_state", self._binder.apply_startup_state)

    # -------------------------------------------------------------------------
    # Guard helpers
    # -------------------------------------------------------------------------

    def _bump_soft_error(self, key: str) -> None:
        self._guard_ops.bump(key)

    def _best_effort(self, key: str, func: Callable[[], None]) -> None:
        self._guard_ops.best_effort(key, func)

    def _read_or_fallback(self, key: str, func: Callable[[], _T], *, fallback: _T) -> _T:
        return self._guard_ops.read_or_fallback(key, func, fallback=fallback)

    # -------------------------------------------------------------------------
    # Initialization helpers
    # -------------------------------------------------------------------------

    def _init_observability(self) -> None:
        """Set up lightweight logs + optional structured status heartbeat."""
        self._hb, self._ch, self._status, _dbg = init_observability(
            "hi_p",
            status_emitter_cls=cast("type[StatusEmitterLike] | None", _StatusEmitterCls),
            status_default_service="hi_p",
        )
        self._last_mode: str = ""
        self._last_estop: bool = False
        self._last_fault: bool = False
        self._last_estate: str = "ESTOP"

        # HiP identity (used for ClaimAxis/ReleaseAxis, etc.)
        # Stable controller identity.
        #
        # The core enforces axis-claim ownership for motion intents.
        # If this id changes every run (random UUID), other components (e.g.
        # joy2intent) cannot reliably stamp matching hip_id into EnableAxis/
        # JogWinch intents, and the core will ignore them as stale.
        #
        # In the future, we can make this per-instance/per-axis via config.
        self._hip_id: str = str(self.hip_id or os.environ.get("STEUERUNG3D_HIP_ID", "hip") or "hip")

    def set_fixed_axis(self, axis_id: str, *, lock_combo: bool = True) -> None:
        self._fixed_axis = normalize_axis_id(axis_id)
        self._lock_axis_combo = bool(lock_combo)
        best_effort(
            lambda: self._hip_runtime.set_fixed_axis(
                self._fixed_axis, lock_combo=self._lock_axis_combo
            )
        )
        if self._fixed_axis:
            best_effort(lambda: self.win.setWindowTitle(f"HMI – HiP ({self._fixed_axis})"))

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _publish_intent(self, intent: Intent) -> None:
        self.intent_out.publish_intent(intent)

    def _emit_birdseye_motion(
        self, *, snap: TelemetrySnapshot, intents: list[Intent], estate: str
    ) -> None:
        self._hip_runtime.emit_birdseye_motion(
            snap=snap,
            intents=list(intents or []),
            estate=str(estate or ""),
            soft_errors=dict(self._soft_errors),
        )

    def _read_ui_inputs(self) -> HipUiInputs:
        return self._read_or_fallback(
            "binder.read_inputs",
            self._binder.read_inputs,
            fallback=HipUiInputs(
                axis_selected="",
                axis_selection_changed=False,
                estop_reset_clicked=False,
                resync_clicked=False,
                param_actions=[],
                param_values={},
            ),
        )

    def _log_runtime_result(self, *, ui_inputs: HipUiInputs, rt_result: HipRuntimeResult) -> None:
        vm: HipViewModel | None = rt_result.view_model
        attached = (
            vm.attach_state.attached if (vm is not None and vm.attach_state is not None) else None
        )
        intents_count = len(rt_result.intents)
        now_s = time.time()
        ui_log_key = (ui_inputs.axis_selected, attached, intents_count)
        if (
            ui_inputs.axis_selection_changed
            or ui_log_key != self._last_ui_log_key
            or now_s >= self._ui_log_next_s
        ):
            log.info(
                "hi_p: ui axis=%r changed=%s attached=%s intents=%d",
                ui_inputs.axis_selected,
                ui_inputs.axis_selection_changed,
                attached,
                intents_count,
            )
            self._last_ui_log_key = ui_log_key
            self._ui_log_next_s = now_s + 1.0

        if vm is not None and not self._dbg_vm_keys_once:
            self._dbg_vm_keys_once = True
            log.info("hi_p: dbg vm_type=%s keys=%s", type(vm).__name__, sorted(vars(vm).keys()))

        if now_s >= self._dbg_next_s:
            self._dbg_next_s = now_s + 1.0
            ast = vm.attach_state if vm is not None else None
            log.info(
                "hi_p: dbg axis=%r attached=%s modal_locked=%s tabs_enabled=%s lifetick_age=%r drive_main=%r pos=%r vel=%r",
                ui_inputs.axis_selected,
                ast.attached if ast is not None else None,
                None,
                ast.tabs_enabled if ast is not None else None,
                vm.lifetick_age if vm is not None else None,
                vm.drive_status.main_text
                if (vm is not None and vm.drive_status is not None)
                else None,
                vm.readouts.pos_text if (vm is not None and vm.readouts is not None) else None,
                vm.readouts.vel_text if (vm is not None and vm.readouts is not None) else None,
            )

    def _apply_runtime_result(self, *, rt_result: HipRuntimeResult) -> bool:
        if rt_result.apply_startup_state:
            self._best_effort("binder.apply_startup_state", self._binder.apply_startup_state)
            return False

        if rt_result.view_model is None:
            return False
        vm = rt_result.view_model

        def _apply_vm() -> None:
            self._binder.apply(vm)

        def _on_apply_error() -> None:
            self._bump_soft_error("binder.apply")
            now_s = time.time()
            last = self._binder_apply_err_last_s
            if now_s - last > 1.0:
                self._binder_apply_err_last_s = now_s
                log.exception("hi_p: binder.apply crashed (continuing).")

        best_effort(_apply_vm, on_error=_on_apply_error)
        return True

    def set_smoke_control_in(self, control_in: UdpHiPSmokeControlIn | None) -> None:
        self._smoke_control_in = control_in

    def _merge_smoke_inputs(self, ui_inputs: HipUiInputs) -> HipUiInputs:
        control_in = self._smoke_control_in
        if control_in is None:
            return ui_inputs
        actions = list(ui_inputs.param_actions or [])
        param_values = {str(k): dict(v) for k, v in dict(ui_inputs.param_values or {}).items()}
        axis_selected = str(ui_inputs.axis_selected or "")
        axis_selection_changed = bool(ui_inputs.axis_selection_changed)
        for command in control_in.drain_commands(limit=50):
            action = str(command.action or "").strip().lower()
            group = str(command.group or "").strip()
            if action in {"edit", "write", "cancel"} and group:
                actions.append(HipParamAction(kind=action, group=group))
            elif action == "edit_write" and group:
                actions.append(HipParamAction(kind="edit", group=group))
                actions.append(HipParamAction(kind="write", group=group))
            if action in {"write", "edit_write"} and group:
                param_values[group] = {
                    str(k): float(v) for k, v in dict(command.values or {}).items()
                }
            if action == "select_axis":
                axis_selected = str(command.group or axis_selected)
                axis_selection_changed = True
        return HipUiInputs(
            axis_selected=axis_selected,
            axis_selection_changed=axis_selection_changed,
            estop_reset_clicked=bool(ui_inputs.estop_reset_clicked),
            resync_clicked=bool(ui_inputs.resync_clicked),
            main_reset_clicked=bool(ui_inputs.main_reset_clicked),
            guider_reset_clicked=bool(ui_inputs.guider_reset_clicked),
            param_actions=actions,
            param_values=param_values,
        )

    def _emit_runtime_outputs(self, *, rt_result: HipRuntimeResult) -> None:
        if rt_result.snap is not None:
            estate = ""
            try:
                banner = rt_result.view_model.banner if rt_result.view_model is not None else None
                estate = str(banner.estate if banner is not None else "")
            except Exception:
                estate = ""
            self._emit_birdseye_motion(
                snap=rt_result.snap,
                intents=list(rt_result.intents or []),
                estate=estate,
            )

        for intent in list(rt_result.intents or []):
            self._publish_intent(intent)

    # -------------------------------------------------------------------------
    # Polling
    # -------------------------------------------------------------------------

    def start_polling(self, *, period_ms: int = 50) -> None:
        self._timer = start_poll_timer(self.win, period_ms=period_ms, callback=self.poll_once)

    def poll_once(self) -> None:
        def _body() -> None:
            with self._wd.tick():
                snaps = self.telemetry_in.drain_telemetry(limit=50)
                self._wd.mark("rx")
                now_ns = time.monotonic_ns()

                ui_inputs = self._merge_smoke_inputs(self._read_ui_inputs())
                rt_inputs = self._hip_runtime.collect_inputs(
                    snaps=snaps, now_ns=now_ns, ui=ui_inputs
                )
                rt_result = self._hip_runtime.tick(inputs=rt_inputs)

                self._log_runtime_result(ui_inputs=ui_inputs, rt_result=rt_result)
                if not self._apply_runtime_result(rt_result=rt_result):
                    return

                self._wd.mark("render")
                self._emit_runtime_outputs(rt_result=rt_result)
                self._wd.mark("hb")

        run_guarded(
            _body,
            on_error=lambda: rl_log_exc(
                "hip.poll_once",
                "HiP poll_once crashed (continuing).",
                logger=log,
                level="error",
            ),
        )
