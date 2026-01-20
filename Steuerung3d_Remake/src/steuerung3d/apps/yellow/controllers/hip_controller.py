from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget


from .bindings import YellowBindings
from .ports import IntentOut, TelemetryIn

from steuerung3d.core.intents import RequestEstopReset  

import logging
log = logging.getLogger("hi_p")


@dataclass
class HiPController:
    """Human Intent Parser (HI-P): Yellow UI in --role ip.

    Responsibilities:
      - translate human interactions -> Intents (IntentOut)
      - render TelemetrySnapshot -> widgets (TelemetryIn)
    """

    win: QWidget
    intent_out: IntentOut
    telemetry_in: TelemetryIn

    def __post_init__(self) -> None:
        self.ui = YellowBindings.from_window(self.win)
        self._seen_first_telem = False

        if self.ui.btn_estop_reset is not None:
            self.ui.btn_estop_reset.clicked.connect(self._on_estop_reset)
            log.info("wired: btnEStopReset -> RequestEstopReset intent")
        else:
            log.warning("btnEStopReset not found in UI")


    def _on_estop_reset(self) -> None:
        intent = RequestEstopReset()
        log.info("tx intent: %s", type(intent).__name__)
        self.intent_out.publish_intent(intent)   # adjust name if your port uses send()/emit()

    def start_polling(self, *, period_ms: int = 50) -> None:
        t = QTimer(self.win)
        t.setInterval(period_ms)
        t.timeout.connect(self.poll_once)
        t.start()
        self._timer = t

    def poll_once(self) -> None:
        snaps = self.telemetry_in.drain_telemetry(limit=50)
        if not snaps:
            return

        snap = snaps[-1]

        if not self._seen_first_telem:
            log.info("rx first telemetry: tick=%s estop=%s fault=%s", snap.tick, snap.estop, snap.fault)
            self._seen_first_telem = True

        log.debug("rx telemetry: tick=%s estop=%s fault=%s", snap.tick, snap.estop, snap.fault)

        # TODO: render into UI
        _ = snap
