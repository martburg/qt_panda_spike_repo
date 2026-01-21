# src/steuerung3d/apps/yellow/controllers/hip_controller.py
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from steuerung3d.core.intents import RequestEstopReset
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.estop_bits import ESTOP_SPECS, decode_estop_word

from .bindings import YellowBindings
from .ports import IntentOut, TelemetryIn

import logging
log = logging.getLogger("hi_p")


@dataclass
class HiPController:
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

    def _set_led(self, w: QWidget | None, on: bool) -> None:
        if w is None:
            return
        if w.property("on") == bool(on):
            return
        w.setProperty("on", bool(on))
        w.style().unpolish(w)
        w.style().polish(w)
        w.update()

    def _set_led_by_name(self, object_name: str | None, on: bool) -> None:
        if not object_name:
            return
        w = self.win.findChild(QWidget, object_name)
        self._set_led(w, on)

    def _on_estop_reset(self) -> None:
        intent = RequestEstopReset()
        log.info("tx intent: %s", type(intent).__name__)
        self.intent_out.publish_intent(intent)

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

        self._render_estop(snap)

    def _render_estop(self, snap: TelemetrySnapshot) -> None:
        word = int(getattr(snap, "estop_status_word", 0))
        logical = decode_estop_word(word)  # invert already applied per spec
        log.debug("render estop word=%s logical=%s", hex(word), logical)

        # Drive all dots declared in ESTOP_SPECS (if present in UI)
        for spec in ESTOP_SPECS.values():
            if not spec.dot:
                continue
            self._set_led_by_name(spec.dot, bool(logical.get(spec.key, False)))
