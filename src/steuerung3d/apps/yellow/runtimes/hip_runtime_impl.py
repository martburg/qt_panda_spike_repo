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
from ..engines.hip.types import HipPresentationData
from ..engines.hip.viewmodel import HipViewModel
from .hip_runtime_viewmodel import assemble_legacy_view_model, assemble_view_model
from .hip_runtime_status import (
    build_hip_birdseye_payload,
    build_hip_motion_debug_snapshot,
    build_hip_status_payload,
)
from .runtime_kernel import emit_runtime_status
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
            if self._dbg_rl.allow("hip_snap_src_empty"):
                self._log.info(
                    "hip snap src=empty now_ns=%s last_rx_ns=%s stale_after_ms=%s apply_startup=%s",
                    now_ns,
                    self._last_rx_ns,
                    self._stale_after_ms,
                    int(apply_startup),
                )
            if self._last_rx_ns is not None:
                age_ms = (now_ns - int(self._last_rx_ns)) / 1_000_000.0
                if age_ms >= float(self._stale_after_ms):
                    self._last_rx_ns = None
                    apply_startup = True
                    self._log.info(
                        "hip snap src=stale age_ms=%.1f stale_after_ms=%s -> apply_startup=1",
                        age_ms,
                        self._stale_after_ms,
                    )
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

        if self._dbg_rl.allow("hip_snap_src_rx"):
            densis_dbg: dict[str, dict[str, object]] = {}
            for axis_key, densi in dict(getattr(snap, "densis", {}) or {}).items():
                densis_dbg[str(axis_key)] = {
                    "online": bool(getattr(densi, "online", False)),
                    "owner": str(getattr(densi, "claimed_by_hip", "") or ""),
                }
            self._log.info(
                "hip snap src=rx rx_count=%s tick=%s core_mode=%s estop=%s fault=%s densis=%s",
                len(snaps),
                getattr(snap, "tick", None),
                getattr(snap, "core_mode", None),
                getattr(snap, "estop", None),
                getattr(snap, "fault", None),
                densis_dbg,
            )

        if not self._seen_first_telem:
            densis_dbg: dict[str, dict[str, object]] = {}
            for axis_key, densi in dict(getattr(snap, "densis", {}) or {}).items():
                densis_dbg[str(axis_key)] = {
                    "online": bool(getattr(densi, "online", False)),
                    "owner": str(getattr(densi, "claimed_by_hip", "") or ""),
                }
            self._log.info(
                "rx first telemetry: tick=%s core_mode=%s estop=%s fault=%s densis=%s",
                getattr(snap, "tick", None),
                getattr(snap, "core_mode", None),
                getattr(snap, "estop", None),
                getattr(snap, "fault", None),
                densis_dbg,
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
        intents = list(engine_result.intents or [])
        txn_events = list(getattr(engine_result, "txn_events", []) or [])

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
            motion_dbg = build_hip_motion_debug_snapshot(runtime=self, snap=snap)
            combo_current = ""
            combo_items: list[str] = []
            try:
                combo_current = str(getattr(vm.axis_combo, "current", "") or "")
                combo_items = [str(x) for x in list(getattr(vm.axis_combo, "items", []) or [])]
            except Exception:
                combo_current = ""
                combo_items = []
            densis_dbg: dict[str, dict[str, object]] = {}
            for axis_key, densi in dict(getattr(snap, "densis", {}) or {}).items():
                densis_dbg[str(axis_key)] = {
                    "online": bool(getattr(densi, "online", False)),
                    "owner": str(getattr(densi, "claimed_by_hip", "") or ""),
                }
            self._log.info(
                "hip motion axis=%s mode=%s legacy=%s owner=%s enabled=%s dm=%s sel=%s sp=%.3f combo_current=%s combo_items=%s snap_tick=%s snap_core_mode=%s densis=%s",
                motion_dbg.motion_axis or "-",
                motion_dbg.core_mode or "-",
                motion_dbg.legacy_mode or "-",
                motion_dbg.owner or "-",
                int(motion_dbg.motion_enabled),
                int(motion_dbg.joy_deadman),
                int(motion_dbg.joy_select_hip),
                motion_dbg.joy_soll_speed,
                combo_current,
                combo_items,
                getattr(snap, "tick", None),
                getattr(snap, "core_mode", None),
                densis_dbg,
            )

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

    def emit_birdseye_motion(
        self,
        *,
        snap: object,
        intents: list[Intent],
        estate: str,
        soft_errors: dict[str, int] | None = None,
    ) -> None:
        if getattr(self, "_status", None) is None:
            return

        payload = build_hip_birdseye_payload(
            runtime=self,
            snap=snap,
            intents=list(intents or []),
            estate=str(estate or ""),
            soft_errors=dict(soft_errors or {}),
        )

        emit_runtime_status(
            self._status,
            level="OK",
            summary=payload.summary,
            fields=payload.fields,
            log=self._log,
            exc_tag="hip.birdseye.emit",
            exc_msg="HiP birds-eye emission failed",
        )

    def _emit_status(self, now_ns: int) -> None:
        # Status emitters may legitimately be falsey (e.g. a test stub that
        # defines __bool__). Only skip emission when we truly don't have one.
        if getattr(self, "_status", None) is None:
            return

        payload = build_hip_status_payload(runtime=self, now_ns=int(now_ns))

        emit_runtime_status(
            self._status,
            level=payload.level,
            summary=payload.summary,
            fields=payload.fields,
            log=self._log,
            exc_tag="hip.status.emit",
            exc_msg="HiP status emission failed",
        )
