from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from steuerung3d.core.intents import SetEstop

from .bindings import YellowBindings
from .ports import IntentOut, TelemetryIn


@dataclass
class HiPController:
    """Human Intent Parser (HI-P): Yellow UI in --role ip.

    Responsibilities:
      - translate human interactions -> Intents (IntentOut)
      - render TelemetrySnapshot -> widgets (TelemetryIn)

    For the first slice we only wire the E-Stop all set/clear buttons.
    """

    win: QWidget
    intent_out: IntentOut
    telemetry_in: TelemetryIn

    def __post_init__(self) -> None:
        self.ui = YellowBindings.from_window(self.win)

        # Wire minimal intents
        if self.ui.btn_estop_all_set is not None:
            self.ui.btn_estop_all_set.clicked.connect(lambda: self.intent_out.send_intent(SetEstop(estop=True)))
        if self.ui.btn_estop_all_clear is not None:
            self.ui.btn_estop_all_clear.clicked.connect(lambda: self.intent_out.send_intent(SetEstop(estop=False)))

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
        # TODO: update LEDs/labels from snap (kept minimal for now)
        # Example future:
        # - EStop LEDs
        # - axis position/velocity labels
        _ = snap
