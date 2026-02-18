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

from dataclasses import dataclass
import logging
import os
import time
import uuid

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from steuerung3d.core.intents import ParamEditBegin
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat
from steuerung3d.util.ratelimit import RateLimiter, rl_log_exc

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter  # type: ignore
except Exception:  # pragma: no cover
    StatusEmitter = None  # type: ignore

from .bindings import YellowBindings
from .ports import IntentOut, TelemetryIn
from .ui_watchdog import PerfWatchdog
from ..binders.hip_qt_binder import HipQtBinder
from ..engines.hip.engine import HipEngine, HipStepInputs, HipStepResult, HipUiInputs, HipViewModel

log = logging.getLogger("hi_p")


@dataclass
class HiPController:
    win: QWidget
    intent_out: IntentOut
    telemetry_in: TelemetryIn

    # If we stop receiving telemetry for this long, we go back to UNKNOWN
    stale_after_ms: int = 500

    def __post_init__(self) -> None:
        self.ui = YellowBindings.from_window(self.win)

        # --- Qt binder (UI-only) ---
        self._binder = HipQtBinder(self.win, log)

        # --- Observability (logging + optional supervisor heartbeat) ---
        self._init_observability()
        self._wd = PerfWatchdog(log, name="hi_p")

        # --- HipEngine shadow mode (no behavior change)
        # Run with: HIP_ENGINE_MODE=shadow python -m steuerung3d.apps.hi_p
        self._hip_engine = HipEngine(hip_id=str(getattr(self, "_hip_id", "") or ""))
        mode = str(os.getenv("HIP_ENGINE_MODE", "old") or "old").strip().lower()
        if mode not in ("old", "shadow", "new"):
            mode = "old"
        self._hip_engine_mode = mode
        self._hip_engine_shadow_rl = RateLimiter(min_interval_s=6.0)

        # Telemetry staleness bookkeeping
        self._seen_first_telem = False
        self._last_rx_ns: int | None = None
        self._timer: QTimer | None = None

        # Axis selection config (pooling/fixed-axis)
        self._fixed_axis: str = ""
        self._lock_axis_combo: bool = False

        # Paint an explicit startup state (unknown dots, no tick, etc.)
        try:
            self._binder.apply_startup_state()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Initialization helpers
    # -------------------------------------------------------------------------

    def _init_observability(self) -> None:
        """Set up lightweight logs + optional structured status heartbeat."""
        self._hb = Heartbeat("hi_p", interval_s=1.0)
        self._ch = ChangeTracker()

        # Structured supervisor heartbeat (side-channel; PLC packets unchanged)
        self._status = StatusEmitter.from_env(default_service="hi_p") if StatusEmitter else None
        self._last_mode: str = ""
        self._last_estop: bool = False
        self._last_fault: bool = False
        self._last_estate: str = "ESTOP"

        # HiP identity (used for ClaimAxis/ReleaseAxis, etc.)
        self._hip_id: str = f"hip-{uuid.uuid4().hex[:8]}"

    def set_fixed_axis(self, axis_id: str, *, lock_combo: bool = True) -> None:
        self._fixed_axis = (axis_id or "").strip()
        self._lock_axis_combo = bool(lock_combo)
        if self._fixed_axis:
            try:
                self.win.setWindowTitle(f"HMI – HiP ({self._fixed_axis})")
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _shadow_log(self, key: str, msg: str) -> None:
        if str(getattr(self, "_hip_engine_mode", "old")) != "shadow":
            return
        if not self._hip_engine_shadow_rl.allow(str(key)):
            return
        log.debug("hip.shadow.%s %s", key, msg)

    def _publish_intent(self, intent: object) -> None:
        self.intent_out.publish_intent(intent)

    def _diff_shadow(self, *, engine_result: HipStepResult, legacy_vm: HipViewModel) -> None:
        legacy_vm_norm = HipEngine.normalize_view_model(legacy_vm)
        engine_vm_norm = HipEngine.normalize_view_model(engine_result.view_model)

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

    def _emit_status(self, now_ns: int) -> None:
        """Emit a compact structured heartbeat for the supervisor birds-eye view.

        This is a best-effort side-channel (UDP JSON) and does not affect PLC telemetry.
        """
        if not getattr(self, "_status", None):
            return
        age_ms: float | None
        if self._last_rx_ns is None:
            age_ms = None
        else:
            age_ms = (now_ns - self._last_rx_ns) / 1_000_000.0

        stale = (age_ms is None) or (age_ms >= float(self.stale_after_ms))
        level = "ERR" if (self._last_estop or self._last_fault) else ("WARN" if stale else "OK")
        axis = str(getattr(self._hip_engine.state, "selected_axis", "") or "") or (self._fixed_axis or "")
        mode = self._last_mode or ""
        age_disp = "NA" if age_ms is None else f"{age_ms:.0f}"
        summary = f"axis={axis or '-'} mode={mode or '-'} age_ms={age_disp}"

        try:
            self._status.emit_every(
                level=level,
                summary=summary,
                fields={
                    "axis": axis,
                    "mode": mode,
                    "age_ms": (-1 if age_ms is None else float(age_ms)),
                    "stale": bool(stale),
                    "estop": bool(self._last_estop),
                    "fault": bool(self._last_fault),
                },
            )
        except Exception:
            # Never let status emission break the UI loop.
            rl_log_exc("hip.status.emit", "HiP status emission failed", logger=log)

    # -------------------------------------------------------------------------
    # Polling
    # -------------------------------------------------------------------------

    def start_polling(self, *, period_ms: int = 50) -> None:
        t = QTimer(self.win)
        t.setInterval(period_ms)
        t.timeout.connect(self.poll_once)
        t.start()
        self._timer = t

    def poll_once(self) -> None:
        try:
            with self._wd.tick():
                snaps = self.telemetry_in.drain_telemetry(limit=50)
                self._wd.mark("rx")
                now_ns = time.monotonic_ns()

                if not snaps:
                    if self._last_rx_ns is not None:
                        age_ms = (now_ns - self._last_rx_ns) / 1_000_000.0
                        if age_ms >= float(self.stale_after_ms):
                            self._last_rx_ns = None
                            try:
                                self._binder.apply_startup_state()
                            except Exception:
                                pass
                    self._emit_status(now_ns)
                    return

                snap = snaps[-1]
                self._last_rx_ns = now_ns

                if not self._seen_first_telem:
                    log.info(
                        "rx first telemetry: tick=%s estop=%s fault=%s",
                        getattr(snap, "tick", None),
                        getattr(snap, "estop", None),
                        getattr(snap, "fault", None),
                    )
                    self._seen_first_telem = True

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
                        pass

                engine_result = self._hip_engine.step(
                    HipStepInputs(
                        snap=snap,
                        hip_id=str(self._hip_id or ""),
                        last_rx_ns=self._last_rx_ns,
                        now_ns=int(now_ns),
                        stale_after_ms=int(self.stale_after_ms),
                        fixed_axis=str(getattr(self, "_fixed_axis", "") or ""),
                        lock_axis_combo=bool(getattr(self, "_lock_axis_combo", False)),
                        last_mode=str(getattr(self, "_last_mode", "") or ""),
                        last_estate=str(getattr(self, "_last_estate", "") or ""),
                        ui=ui_inputs,
                        core_acks=list(getattr(snap, "core_acks", []) or []),
                    )
                )

                if getattr(self, "_binder", None) is not None:
                    try:
                        self._binder.apply(engine_result.view_model)
                    except Exception:
                        pass
                self._wd.mark("render")

                self._hb.inc("rx_telem", len(snaps))
                mode_v = str(getattr(snap, "mode", ""))
                estop_v = bool(getattr(snap, "estop", False))
                fault_v = bool(getattr(snap, "fault", False))
                self._last_mode = mode_v
                self._last_estop = estop_v
                self._last_fault = fault_v
                try:
                    self._last_estate = str(getattr(engine_result.view_model.banner, "estate", "ESTOP") or "ESTOP")
                except Exception:
                    self._last_estate = "ESTOP"

                if self._hip_engine_mode == "shadow":
                    self._diff_shadow(engine_result=engine_result, legacy_vm=engine_result.legacy_view_model)

                if engine_result.view_model.param_writeback_values and engine_result.view_model.param_writeback_group:
                    log.info(
                        "param guards adjusted %s values (writing back to UI)",
                        engine_result.view_model.param_writeback_group,
                    )

                for intent in engine_result.intents:
                    if isinstance(intent, ParamEditBegin):
                        log.info(
                            "tx intent: %s group=%s req_id=%s session=%s",
                            type(intent).__name__,
                            getattr(intent, "group", ""),
                            getattr(intent, "req_id", ""),
                            getattr(intent, "session_id", ""),
                        )
                    self._publish_intent(intent)

                for ev in list(getattr(engine_result, "txn_events", []) or []):
                    if getattr(ev, "action", "") == "giveup":
                        log.error("txn give up: %s after %s retries (%s)", ev.req_id, ev.retries, ev.intent_type)
                    else:
                        log.warning("txn resend: %s retry=%s %s", ev.req_id, ev.retries, ev.intent_type)

                if getattr(engine_result, "resync_ignored", False):
                    log.warning(
                        "ignored RequestResync (allowed only when system idle), %s",
                        str(getattr(engine_result, "resync_block_reason", "") or ""),
                    )

                if self._ch.changed("mode", mode_v):
                    log.info("mode=%s", mode_v)
                if self._ch.changed("estop", estop_v):
                    log.info("estop=%s", estop_v)
                if self._ch.changed("fault", fault_v):
                    log.info("fault=%s", fault_v)

                self._hb.set("tick", int(getattr(snap, "tick", 0) or 0))
                self._hb.set("mode", mode_v)
                self._hb.set("estop", estop_v)
                self._hb.set("fault", fault_v)
                axis = str(getattr(self._hip_engine.state, "selected_axis", "") or "")
                if axis:
                    self._hb.set("axis", axis)
                self._hb.emit(log)
                self._wd.mark("hb")
        except Exception:
            rl_log_exc("hip.poll_once", "HiP poll_once crashed (continuing).", logger=log, level="error")