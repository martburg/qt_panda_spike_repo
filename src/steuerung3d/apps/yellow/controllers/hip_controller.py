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
from typing import cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat
from steuerung3d.util.ratelimit import rl_log_exc

from ..binders.hip_qt_binder import HipQtBinder
from ..engines.hip.engine import HipEngine, HipUiInputs
from ..ports import IntentOut, TelemetryIn
from ..qtutil.bindings import YellowBindings
from ..qtutil.perf_watchdog import PerfWatchdog
from ..runtimes.hip_runtime import HipRuntime
from .controller_utils import StatusEmitterLike, init_observability, run_guarded, start_poll_timer

_StatusEmitterCls: type[object] | None

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter as _StatusEmitter  # type: ignore

    _StatusEmitterCls = _StatusEmitter
except Exception:  # pragma: no cover
    _StatusEmitterCls = None


log = logging.getLogger("hi_p")


@dataclass
class HiPController:
    win: QWidget
    intent_out: IntentOut
    telemetry_in: TelemetryIn

    shadow_mode: str | None = None
    hip_id: str = ""

    # If we stop receiving telemetry for this long, we go back to UNKNOWN
    stale_after_ms: int = 500

    _dbg_next_s = 0.0
    _dbg_vm_keys_once: bool = False

    # Binder apply throttling (avoid log spam on repeated UI update errors)
    _binder_apply_err_last_s: float = 0.0

    # Late-initialized internal members (kept out of __init__ signature)
    _hb: Heartbeat = field(init=False)
    _ch: ChangeTracker = field(init=False)
    _status: StatusEmitterLike | None = field(init=False, default=None)
    _timer: QTimer | None = field(init=False, default=None)

    # Qt-free runtime/engine
    _hip_engine: HipEngine = field(init=False)
    _hip_runtime: HipRuntime = field(init=False)

    def __post_init__(self) -> None:
        self.ui = YellowBindings.from_window(self.win)

        # Soft-error counters for swallowed exceptions (binder/UI)
        self._soft_errors: dict[str, int] = {}

        # --- Qt binder (UI-only) ---
        self._binder = HipQtBinder(self.win, log)

        # --- Observability (logging + optional supervisor heartbeat) ---
        self._init_observability()
        self._wd = PerfWatchdog(log, name="hi_p")

        # --- HiP runtime (Qt-free orchestration)
        self._hip_engine = HipEngine(hip_id=str(getattr(self, "_hip_id", "") or ""))
        self._hip_runtime = HipRuntime(
            engine=self._hip_engine,
            hb=self._hb,
            ch=self._ch,
            status=self._status,
            stale_after_ms=self.stale_after_ms,
            log=log,
            hip_id=str(getattr(self, "_hip_id", "") or ""),
            shadow_mode=self.shadow_mode,
        )

        # self._timer is declared as a dataclass field for typing; value set here.
        self._timer = None

        # Axis selection config (pooling/fixed-axis)
        self._fixed_axis: str = ""
        self._lock_axis_combo: bool = False

        # Paint an explicit startup state (unknown dots, no tick, etc.)
        try:
            self._binder.apply_startup_state()
        except Exception:
            self._soft_errors["binder.apply_startup_state"] = (
                int(self._soft_errors.get("binder.apply_startup_state", 0)) + 1
            )

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
        try:
            self._hip_runtime.set_fixed_axis(self._fixed_axis, lock_combo=self._lock_axis_combo)
        except Exception:
            pass
        if self._fixed_axis:
            try:
                self.win.setWindowTitle(f"HMI – HiP ({self._fixed_axis})")
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _publish_intent(self, intent: Intent) -> None:
        self.intent_out.publish_intent(intent)

    def _emit_birdseye_motion(
        self, *, snap: TelemetrySnapshot, intents: list[Intent], estate: str
    ) -> None:
        status = getattr(self, "_status", None)
        if status is None:
            return

        axis_selected = ""
        try:
            axis_selected = str(getattr(self._hip_engine.state, "selected_axis", "") or "")
        except Exception:
            axis_selected = ""
        if not axis_selected:
            axis_selected = str(getattr(self, "_fixed_axis", "") or "")

        joy = None
        try:
            joy = getattr(self._hip_engine.state, "joy", None)
        except Exception:
            joy = None
        if joy is None:
            joy = getattr(snap, "joy", None)

        joy_soll_speed_norm = 0.0
        dm = False
        sel = False
        try:
            raw_sp = float(getattr(joy, "soll_speed", 0.0) or 0.0)
            dm = bool(getattr(joy, "deadman", False))

            selected_axes = tuple(getattr(joy, "selected_axes", ()) or ())
            selected_axis_set = {str(x).strip() for x in selected_axes if str(x).strip()}

            if selected_axis_set:
                sel = bool(axis_selected) and axis_selected in selected_axis_set
            else:
                sel = False

            joy_soll_speed_norm = float(raw_sp if sel else 0.0)
        except Exception:
            joy_soll_speed_norm = 0.0
            dm = False
            sel = False

        velmax = 0.0
        try:
            params = snap.params or {}
            velmax = float(params.get("VelMax", 0.0) or 0.0)
        except Exception:
            velmax = 0.0
        if velmax < 0.0:
            velmax = 0.0

        joy_rate_mps = joy_soll_speed_norm * velmax if velmax > 0.0 else 0.0

        estop = bool(snap.estop)
        fault = bool(snap.fault)
        core_mode = str(snap.core_mode or "")
        armed = bool(str(estate or "").upper() in ("ARMED", "READY"))
        ready = bool(str(estate or "").upper() == "READY")

        enable: bool | None = None
        try:
            if axis_selected:
                ax = snap.axes.get(axis_selected)
                if ax is not None:
                    # prefer what core is commanding (echoed for UI)
                    enable = (
                        bool(ax.enable_cmd)
                        if hasattr(ax, "enable_cmd")
                        else bool(getattr(ax, "enabled", False))
                    )
        except Exception:
            enable = None

        types = []
        try:
            types = sorted({type(i).__name__ for i in (intents or [])})
        except Exception:
            types = []
        intents_out_types = ",".join(types)
        intents_out_count = int(len(intents or []))

        summary = (
            f"hip axis={axis_selected or '-'} core_mode={core_mode or '-'} "
            f"legacy_mode={estate or '-'} dm={int(dm)} sel={int(sel)} "
            f"estop={int(estop)} v={joy_rate_mps:+.2f}m/s out=[{intents_out_types}]"
        )

        fields: dict[str, object] = {
            "component": "hip",
            "axis_selected": str(axis_selected or ""),
            "deadman": bool(dm),
            "select_hip": bool(sel),
            "joy_soll_speed_norm": float(joy_soll_speed_norm),
            "velmax": float(velmax),
            "joy_rate_mps": float(joy_rate_mps),
            "intents_out_types": str(intents_out_types),
            "intents_out_count": int(intents_out_count),
            "estop": bool(estop),
            "fault": bool(fault),
            "mode": str(core_mode),
            "estate": str(estate or ""),
            "armed": bool(armed),
            "ready": bool(ready),
            "sel": bool(sel),
            "dm": bool(dm),
        }
        try:
            soft = dict(getattr(self, "_soft_errors", {}) or {})
            fields["soft_errors_total"] = int(sum(int(v) for v in soft.values()))
            fields["soft_errors_by_key"] = {str(k): int(v) for k, v in soft.items()}
        except Exception:
            pass
        if enable is not None:
            fields["enable"] = bool(enable)

        try:
            status.emit_every(level="OK", summary=summary, fields=fields)
        except Exception:
            return

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

                ui_inputs = HipUiInputs(
                    axis_selected="",
                    axis_selection_changed=False,
                    estop_reset_clicked=False,
                    resync_clicked=False,
                    param_actions=[],
                    param_values={},
                )
                if getattr(self, "_binder", None) is not None:
                    try:
                        ui_inputs = self._binder.read_inputs()
                    except Exception:
                        self._soft_errors["binder.read_inputs"] = (
                            int(self._soft_errors.get("binder.read_inputs", 0)) + 1
                        )

                rt_inputs = self._hip_runtime.collect_inputs(
                    snaps=snaps, now_ns=now_ns, ui=ui_inputs
                )
                rt_result = self._hip_runtime.tick(inputs=rt_inputs)

                log.info(
                    "hi_p: ui axis=%r changed=%s attached=%s intents=%d",
                    ui_inputs.axis_selected,
                    ui_inputs.axis_selection_changed,
                    getattr(rt_result.view_model.attach_state, "attached", None)
                    if rt_result.view_model
                    else None,
                    len(rt_result.intents) if hasattr(rt_result, "intents") else -1,
                )

                vm = rt_result.view_model
                if vm is not None and not getattr(self, "_dbg_vm_keys_once", False):
                    self._dbg_vm_keys_once = True
                    log.info(
                        "hi_p: dbg vm_type=%s keys=%s", type(vm).__name__, sorted(vars(vm).keys())
                    )

                now_s = time.time()
                if now_s >= getattr(self, "_dbg_next_s", 0.0):
                    self._dbg_next_s = now_s + 1.0

                    vm = rt_result.view_model
                    ast = getattr(vm, "attach_state", None)

                    log.info(
                        "hi_p: dbg axis=%r attached=%s modal_locked=%s tabs_enabled=%s "
                        "lifetick_age=%r drive_main=%r pos=%r vel=%r",
                        ui_inputs.axis_selected,
                        getattr(ast, "attached", None),
                        getattr(ui_inputs, "modal_locked", None),
                        getattr(ast, "tabs_enabled", None),
                        getattr(vm, "lifetick_age", None),
                        getattr(vm, "main_drive_status_text", None),
                        getattr(vm, "pos_text", None),
                        getattr(vm, "vel_text", None),
                    )

                if rt_result.apply_startup_state:
                    if getattr(self, "_binder", None) is not None:
                        try:
                            self._binder.apply_startup_state()
                        except Exception:
                            self._soft_errors["binder.apply_startup_state"] = (
                                int(self._soft_errors.get("binder.apply_startup_state", 0)) + 1
                            )
                    return

                if rt_result.view_model is None:
                    return

                if getattr(self, "_binder", None) is not None:
                    try:
                        self._binder.apply(rt_result.view_model)
                    except Exception:
                        self._soft_errors["binder.apply"] = (
                            int(self._soft_errors.get("binder.apply", 0)) + 1
                        )
                        now_s = time.time()
                        last = getattr(self, "_binder_apply_err_last_s", 0.0)
                        if now_s - last > 1.0:  # rate-limit so logs don't explode
                            self._binder_apply_err_last_s = now_s
                            log.exception("hi_p: binder.apply crashed (continuing).")

                self._wd.mark("render")

                if rt_result.snap is not None:
                    estate = ""
                    try:
                        estate = str(
                            getattr(getattr(rt_result.view_model, "banner", None), "estate", "")
                            or ""
                        )
                    except Exception:
                        estate = ""
                    self._emit_birdseye_motion(
                        snap=rt_result.snap,
                        intents=list(rt_result.intents or []),
                        estate=estate,
                    )

                for intent in list(rt_result.intents or []):
                    self._publish_intent(intent)

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
