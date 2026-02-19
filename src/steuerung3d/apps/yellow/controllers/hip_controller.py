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
import time
import uuid

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat
from steuerung3d.util.ratelimit import rl_log_exc

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter  # type: ignore
except Exception:  # pragma: no cover
    StatusEmitter = None  # type: ignore

from ..qtutil.bindings import YellowBindings
from ..ports import IntentOut, TelemetryIn
from .ui_watchdog import PerfWatchdog
from ..binders.hip_qt_binder import HipQtBinder
from ..engines.hip.engine import HipEngine, HipUiInputs
from ..runtimes.hip_runtime import HipRuntime

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
        )

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

    def _publish_intent(self, intent: object) -> None:
        self.intent_out.publish_intent(intent)

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

                rt_inputs = self._hip_runtime.collect_inputs(snaps=snaps, now_ns=now_ns, ui=ui_inputs)
                rt_result = self._hip_runtime.tick(inputs=rt_inputs)

                if rt_result.apply_startup_state:
                    if getattr(self, "_binder", None) is not None:
                        try:
                            self._binder.apply_startup_state()
                        except Exception:
                            pass
                    return

                if rt_result.view_model is None:
                    return

                if getattr(self, "_binder", None) is not None:
                    try:
                        self._binder.apply(rt_result.view_model)
                    except Exception:
                        pass
                self._wd.mark("render")

                for intent in list(rt_result.intents or []):
                    self._publish_intent(intent)

                self._wd.mark("hb")
        except Exception:
            rl_log_exc("hip.poll_once", "HiP poll_once crashed (continuing).", logger=log, level="error")