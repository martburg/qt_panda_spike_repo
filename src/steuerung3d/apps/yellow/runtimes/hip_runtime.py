"""Qt-free runtime seam for Hip.

Responsibilities:
- Drain telemetry snapshots (provided by controller).
- Call HipEngine.
- Emit non-UI logs/heartbeat/status.

UI rendering stays in the controller.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from steuerung3d.core.intents import ParamEditBegin
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.core.joy_state import JoyState
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat
from steuerung3d.util.ratelimit import RateLimiter

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter  # type: ignore
except Exception:  # pragma: no cover
    StatusEmitter = None  # type: ignore

from ..domain.param_txn import RetryEvent
from ..domain.ui_estop import infer_estop_profile
from ..engines.hip.engine import HipEngine, HipStepInputs, HipStepResult, HipUiInputs
from ..engines.hip.types import HipPresentationData
from ..engines.hip.viewmodel import HipViewModel
from ..panels.hip.hip_banner_vm import compute_hip_banner_vm
from ..panels.hip.hip_estop_vm import compute_hip_estop_vm
from ..panels.hip.hip_header_dots_vm import compute_hip_header_dots_vm
from .runtime_utils import (
    compute_age_ms,
    compute_status_level,
    compute_stale,
    emit_status,
    format_age_ms,
)


@dataclass(frozen=True)
class HipRuntimeInputs:
    snaps: list[TelemetrySnapshot]
    now_ns: int
    ui: HipUiInputs


@dataclass(frozen=True)
class HipRuntimeResult:
    snap: TelemetrySnapshot | None
    engine_result: HipStepResult | None
    view_model: HipViewModel | None
    intents: list[object]
    txn_events: list[RetryEvent]
    resync_ignored: bool
    resync_block_reason: str
    apply_startup_state: bool
    rx_count: int


class HipRuntime:
    """Qt-free runtime orchestrator for HiP."""

    def __init__(
        self,
        *,
        engine: HipEngine,
        hb: Heartbeat,
        ch: ChangeTracker,
        status=None,
        stale_after_ms: int,
        log: logging.Logger,
        hip_id: str,
        shadow_mode: str | None = None,
    ) -> None:
        self.engine = engine
        self._hb = hb
        self._ch = ch
        self._status = status
        self._stale_after_ms = int(stale_after_ms)
        self._log = log
        self._hip_id = str(hip_id or "")

        mode = shadow_mode
        if mode is None:
            mode = "old"
        mode = str(mode or "old").strip().lower()
        if mode not in ("old", "shadow", "new"):
            mode = "old"
        self._shadow_mode = mode
        self._shadow_rl = RateLimiter(min_interval_s=6.0)

        self._last_rx_ns: int | None = None
        self._seen_first_telem = False
        self._last_mode: str = ""
        self._last_estop: bool = False
        self._last_fault: bool = False
        self._last_estate: str = "ESTOP"

        self._fixed_axis: str = ""
        self._lock_axis_combo: bool = False

    def set_fixed_axis(self, axis_id: str, *, lock_combo: bool = True) -> None:
        self._fixed_axis = (axis_id or "").strip()
        self._lock_axis_combo = bool(lock_combo)

    def collect_inputs(
        self,
        *,
        snaps: list[TelemetrySnapshot],
        now_ns: int,
        ui: HipUiInputs,
    ) -> HipRuntimeInputs:
        return HipRuntimeInputs(snaps=list(snaps or []), now_ns=int(now_ns), ui=ui)

    def tick(self, *, inputs: HipRuntimeInputs) -> HipRuntimeResult:
        snaps = list(inputs.snaps or [])
        now_ns = int(inputs.now_ns)
        apply_startup = False

        if not snaps:
            if self._last_rx_ns is not None:
                age_ms = (now_ns - int(self._last_rx_ns)) / 1_000_000.0
                if age_ms >= float(self._stale_after_ms):
                    self._last_rx_ns = None
                    apply_startup = True
            self._emit_status(now_ns)
            return HipRuntimeResult(
                snap=None,
                engine_result=None,
                view_model=None,
                intents=[],
                txn_events=[],
                resync_ignored=False,
                resync_block_reason="",
                apply_startup_state=apply_startup,
                rx_count=0,
            )

        snap = snaps[-1]
        self._last_rx_ns = now_ns

        if not self._seen_first_telem:
            self._log.info(
                "rx first telemetry: tick=%s estop=%s fault=%s",
                getattr(snap, "tick", None),
                getattr(snap, "estop", None),
                getattr(snap, "fault", None),
            )
            self._seen_first_telem = True

        engine_result = self.engine.step(
            HipStepInputs(
                snap=snap,
                hip_id=self._hip_id,
                last_rx_ns=self._last_rx_ns,
                now_ns=now_ns,
                stale_after_ms=int(self._stale_after_ms),
                fixed_axis=str(self._fixed_axis or ""),
                lock_axis_combo=bool(self._lock_axis_combo),
                last_mode=str(self._last_mode or ""),
                last_estate=str(self._last_estate or ""),
                ui=inputs.ui,
                core_acks=list(getattr(snap, "core_acks", []) or []),
                joy=getattr(snap, "joy", JoyState()),
            )
        )

        vm = self._assemble_view_model(engine_result.presentation)
        legacy_vm = self._assemble_legacy_view_model(engine_result.presentation)

        self._hb.inc("rx_telem", len(snaps))
        mode_v = str(getattr(snap, "core_mode", ""))
        estop_v = bool(getattr(snap, "estop", False))
        fault_v = bool(getattr(snap, "fault", False))
        self._last_mode = mode_v
        self._last_estop = estop_v
        self._last_fault = fault_v
        try:
            self._last_estate = str(getattr(vm.banner, "estate", "ESTOP") or "ESTOP")
        except Exception:
            self._last_estate = "ESTOP"

        if self._shadow_mode == "shadow":
            self._diff_shadow(engine_vm=vm, legacy_vm=legacy_vm)

        if vm.param_writeback_values and vm.param_writeback_group:
            self._log.info(
                "param guards adjusted %s values (writing back to UI)",
                vm.param_writeback_group,
            )

        intents = list(engine_result.intents or [])
        for intent in intents:
            if isinstance(intent, ParamEditBegin):
                self._log.info(
                    "tx intent: %s group=%s req_id=%s session=%s",
                    type(intent).__name__,
                    getattr(intent, "group", ""),
                    getattr(intent, "req_id", ""),
                    getattr(intent, "session_id", ""),
                )

        txn_events = list(getattr(engine_result, "txn_events", []) or [])
        for ev in txn_events:
            if getattr(ev, "action", "") == "giveup":
                self._log.error("txn give up: %s after %s retries (%s)", ev.req_id, ev.retries, ev.intent_type)
            else:
                self._log.warning("txn resend: %s retry=%s %s", ev.req_id, ev.retries, ev.intent_type)

        if getattr(engine_result, "resync_ignored", False):
            self._log.warning(
                "ignored RequestResync (allowed only when system idle), %s",
                str(getattr(engine_result, "resync_block_reason", "") or ""),
            )

        if self._ch.changed("core_mode", mode_v):
            self._log.info("core_mode=%s", mode_v)
        if self._ch.changed("estop", estop_v):
            self._log.info("estop=%s", estop_v)
        if self._ch.changed("fault", fault_v):
            self._log.info("fault=%s", fault_v)

        self._hb.set("tick", int(getattr(snap, "tick", 0) or 0))
        self._hb.set("core_mode", mode_v)
        self._hb.set("estop", estop_v)
        self._hb.set("fault", fault_v)
        axis = str(getattr(self.engine.state, "selected_axis", "") or "")
        if axis:
            self._hb.set("axis", axis)
        self._hb.emit(self._log)

        self._emit_status(now_ns)

        return HipRuntimeResult(
            snap=snap,
            engine_result=engine_result,
            view_model=vm,
            intents=intents,
            txn_events=txn_events,
            resync_ignored=bool(getattr(engine_result, "resync_ignored", False)),
            resync_block_reason=str(getattr(engine_result, "resync_block_reason", "") or ""),
            apply_startup_state=False,
            rx_count=len(snaps),
        )

    def _shadow_log(self, key: str, msg: str) -> None:
        if str(self._shadow_mode) != "shadow":
            return
        if not self._shadow_rl.allow(str(key)):
            return
        self._log.debug("hip.shadow.%s %s", key, msg)

    def _diff_shadow(self, *, engine_vm: HipViewModel, legacy_vm: HipViewModel) -> None:
        legacy_vm_norm = HipEngine.normalize_view_model(legacy_vm)
        engine_vm_norm = HipEngine.normalize_view_model(engine_vm)

        keys = (
            "tick_text",
            "age_ms",
            "stale",
            "lifetick_age",
            "online_state",
            "estop",
            "fault",
            "drive_status_summary",
        )
        legacy_subset = {k: legacy_vm_norm.get(k) for k in keys}
        engine_subset = {k: engine_vm_norm.get(k) for k in keys}
        if legacy_subset != engine_subset:
            self._shadow_log(
                "view_model",
                f"legacy={legacy_subset} engine={engine_subset}",
            )

    @staticmethod
    def _assemble_legacy_view_model(pres: HipPresentationData) -> HipViewModel:
        return HipViewModel(
            tick_text=str(pres.tick_text),
            age_ms=pres.age_ms,
            stale=bool(pres.stale),
            lifetick_age=pres.lifetick_age,
            online_state=pres.online_state,
            estop=bool(pres.estop),
            fault=bool(pres.fault),
            drive_status_summary=str(pres.drive_status_summary or ""),
        )

    @staticmethod
    def _assemble_view_model(pres: HipPresentationData) -> HipViewModel:
        banner = compute_hip_banner_vm(
            estop_word=int(pres.estop_word),
            within_brake_grace=bool(pres.within_banner),
        )

        def _brake_ok_display(raw: bool) -> bool:
            if bool(pres.taster) and bool(pres.within_brake):
                return True
            return bool(raw)

        header_dots = compute_hip_header_dots_vm(
            online_state=pres.online_state,
            taster=bool(pres.taster),
            ready=bool(pres.logical.get("ready", False)),
            brk1_raw=bool(pres.logical.get("brk1_ok", False)),
            brk2_raw=bool(pres.logical.get("brk2_ok", False)),
            brake_ok_display=_brake_ok_display,
        )

        profile = infer_estop_profile(pres.logical)
        estop_state = compute_hip_estop_vm(
            logical=pres.logical,
            taster=bool(pres.taster),
            attached=bool(pres.attached),
            brake_ok_display=_brake_ok_display,
            profile=profile,
            prev_profile=str(pres.prev_estop_profile or ""),
        )

        return HipViewModel(
            tick_text=str(pres.tick_text),
            age_ms=pres.age_ms,
            stale=bool(pres.stale),
            lifetick_age=pres.lifetick_age,
            online_state=pres.online_state,
            estop=bool(pres.estop),
            fault=bool(pres.fault),
            drive_status_summary=str(pres.drive_status_summary or ""),
            joy_deadman=bool(pres.joy_deadman),
            joy_select_hip=bool(pres.joy_select_hip),
            joy_soll_speed=float(pres.joy_soll_speed),
            banner=banner,
            header_dots=header_dots,
            drive_status=pres.drive_status,
            estop_state=estop_state,
            readouts=pres.readouts,
            cut_markers=pres.cut_markers,
            attach_state=pres.attach_state,
            attach_combo=pres.attach_combo,
            param_ui=pres.param_ui,
            param_values=dict(pres.param_values or {}),
            param_freeze_group=str(pres.param_freeze_group or ""),
            limit_values=dict(pres.limit_values or {}),
            param_writeback_group=str(pres.param_writeback_group or ""),
            param_writeback_values=dict(pres.param_writeback_values or {}),
            param_writeback_message=str(pres.param_writeback_message or ""),
            param_commit_dialog=pres.param_commit_dialog,
        )

    def _emit_status(self, now_ns: int) -> None:
        if not getattr(self, "_status", None):
            return

        age_ms = compute_age_ms(int(now_ns), self._last_rx_ns)
        stale = compute_stale(age_ms, self._stale_after_ms)
        level = compute_status_level(self._last_estop, self._last_fault, stale)
        axis = str(getattr(self.engine.state, "selected_axis", "") or "") or (self._fixed_axis or "")
        estate = str(self._last_estate or "")
        mode = estate or (self._last_mode or "")
        armed = bool(str(estate or "").upper() in ("ARMED", "READY"))
        ready = bool(str(estate or "").upper() == "READY")
        age_disp = format_age_ms(age_ms)
        joy = getattr(self.engine.state, "joy", JoyState())
        dm = 1 if bool(getattr(joy, "deadman", False)) else 0
        sel = 1 if bool(getattr(joy, "select_hip", False)) else 0
        sp = float(getattr(joy, "soll_speed", 0.0))
        summary = f"axis={axis or '-'} mode={mode or '-'} age_ms={age_disp} JOY dm={dm} sel={sel} sp={sp:+.2f}"

        emit_status(
            self._status,
            level=level,
            summary=summary,
            fields={
                "axis": axis,
                "mode": mode,
                "estate": str(estate or ""),
                "armed": bool(armed),
                "ready": bool(ready),
                "age_ms": (-1 if age_ms is None else float(age_ms)),
                "stale": bool(stale),
                "estop": bool(self._last_estop),
                "fault": bool(self._last_fault),
                "joy_deadman": bool(getattr(joy, "deadman", False)),
                "joy_select_hip": bool(getattr(joy, "select_hip", False)),
                "joy_soll_speed": float(sp),
            },
            log=self._log,
            exc_tag="hip.status.emit",
            exc_msg="HiP status emission failed",
        )
