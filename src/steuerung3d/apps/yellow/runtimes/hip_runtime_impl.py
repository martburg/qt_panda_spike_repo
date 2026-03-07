"""Qt-free runtime seam for Hip.

Responsibilities:
- Drain telemetry snapshots (provided by controller).
- Call HipEngine.
- Emit non-UI logs/heartbeat/status.

UI rendering stays in the controller.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.intents import Intent, ParamEditBegin
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry import TelemetrySnapshot
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
from ..engines.hip.intent_policy import get_claim_owner
from ..engines.hip.types import HipPresentationData
from ..engines.hip.viewmodel import HipViewModel
from .hip_runtime_viewmodel import assemble_legacy_view_model, assemble_view_model
from .runtime_kernel import compute_health, emit_runtime_status, with_health_fields
from .runtime_utils import StatusEmitterLike


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
    intents: list[Intent]
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
        self._stale_after_ms = int(stale_after_ms)
        self._log = log
        self._status: StatusEmitterLike | None = status
        self._hip_id = str(hip_id or "")

        mode = shadow_mode
        if mode is None:
            mode = "old"
        mode = str(mode or "old").strip().lower()
        if mode not in ("old", "shadow", "new"):
            mode = "old"
        self._shadow_mode = mode
        self._shadow_rl = RateLimiter(min_interval_s=6.0)
        self._dbg_rl = RateLimiter(min_interval_s=1.0)

        self._last_rx_ns: int | None = None
        self._seen_first_telem = False
        self._last_mode: str = ""
        self._last_estop: bool = False
        self._last_fault: bool = False
        self._last_estate: str = "ESTOP"

        self._fixed_axis: str = ""
        self._lock_axis_combo: bool = False

    def set_fixed_axis(self, axis_id: str, *, lock_combo: bool = True) -> None:
        self._fixed_axis = normalize_axis_id(axis_id)
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

        if self._dbg_rl.allow("hip_motion_dbg"):
            axes = snap.axes
            # snap.axes is a Mapping[str, AxisTelemetry]

            axis_ids = sorted(list(axes.keys()))
            selected_axis = str(getattr(self.engine.state, "selected_axis", "") or "")
            fixed_axis = str(self._fixed_axis or "")
            motion_axis = selected_axis or fixed_axis
            if not motion_axis and len(axis_ids) == 1:
                motion_axis = axis_ids[0]

            owner = get_claim_owner(snap, motion_axis) if motion_axis else ""
            core_mode = str(getattr(snap, "core_mode", ""))
            legacy_mode = str(getattr(snap, "mode", ""))
            joy = getattr(snap, "joy", JoyState())
            dm = bool(getattr(joy, "deadman", False))
            raw_sp = float(getattr(joy, "soll_speed", 0.0) or 0.0)
            selected_axes = tuple(getattr(joy, "selected_axes", ()) or ())
            selected_axis_set = {str(x).strip() for x in selected_axes if str(x).strip()}

            if selected_axis_set:
                sel = bool(motion_axis) and motion_axis in selected_axis_set
            else:
                sel = False

            sp = float(raw_sp if sel else 0.0)

            motion_enabled = (
                bool(motion_axis)
                and core_mode.upper() == "LIVE"
                and owner == self._hip_id
                and dm
                and sel
            )
            self._log.info(
                "hip_motion_dbg core_mode=%s legacy_mode=%s dm=%s sel=%s sp=%.3f motion_enabled=%s axis=%s owner=%s",
                core_mode,
                legacy_mode,
                int(dm),
                int(sel),
                sp,
                int(motion_enabled),
                motion_axis or "",
                owner,
            )

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
                self._log.error(
                    "txn give up: %s after %s retries (%s)", ev.req_id, ev.retries, ev.intent_type
                )
            else:
                self._log.warning(
                    "txn resend: %s retry=%s %s", ev.req_id, ev.retries, ev.intent_type
                )

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
        return assemble_legacy_view_model(pres)

    @staticmethod
    def _assemble_view_model(pres: HipPresentationData) -> HipViewModel:
        # Keep local import of infer_estop_profile in this module for stability.
        _ = infer_estop_profile
        return assemble_view_model(pres)

    def _emit_status(self, now_ns: int) -> None:
        if not getattr(self, "_status", None):
            return

        h = compute_health(
            now_ns=int(now_ns),
            last_rx_ns=self._last_rx_ns,
            stale_after_ms=self._stale_after_ms,
            seen_first_rx=bool(self._seen_first_telem),
            estop=bool(self._last_estop),
            fault=bool(self._last_fault),
        )
        axis = str(getattr(self.engine.state, "selected_axis", "") or "") or (
            self._fixed_axis or ""
        )
        estate = str(self._last_estate or "")
        mode = str(self._last_mode or "")
        armed = bool(str(estate or "").upper() in ("ARMED", "READY"))
        ready = bool(str(estate or "").upper() == "READY")
        age_disp = str(getattr(h, "age_disp", "") or "")
        joy = getattr(self.engine.state, "joy", JoyState())
        dm_bool = bool(getattr(joy, "deadman", False))
        raw_sp = float(getattr(joy, "soll_speed", 0.0) or 0.0)
        selected_axes = tuple(getattr(joy, "selected_axes", ()) or ())
        selected_axis_set = {str(x).strip() for x in selected_axes if str(x).strip()}

        if selected_axis_set:
            sel_bool = bool(axis) and axis in selected_axis_set
        else:
            sel_bool = False

        sp = float(raw_sp if sel_bool else 0.0)
        dm = 1 if dm_bool else 0
        sel = 1 if sel_bool else 0
        summary = (
            f"axis={axis or '-'} core_mode={mode or '-'} legacy_mode={estate or '-'} "
            f"age_ms={age_disp} JOY dm={dm} sel={sel} sp={sp:+.2f}"
        )

        fields = with_health_fields(
            {
                "axis": axis,
                "mode": mode,
                "estate": str(estate or ""),
                "armed": bool(armed),
                "ready": bool(ready),
                "joy_deadman": bool(dm_bool),
                "joy_select_hip": bool(sel_bool),
                "joy_soll_speed": float(sp),
            },
            health=h,
            estop=bool(self._last_estop),
            fault=bool(self._last_fault),
        )

        emit_runtime_status(
            self._status,
            level=str(getattr(h, "level", "") or ""),
            summary=summary,
            fields=fields,
            log=self._log,
            exc_tag="hip.status.emit",
            exc_msg="HiP status emission failed",
        )
