# src/steuerung3d/apps/yellow/controllers/hip_controller.py
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from steuerung3d.core.intents import RequestEstopReset
from steuerung3d.core.telemetry import TelemetrySnapshot





from steuerung3d.protocol.estop_bits import (
    ESTOP_SPECS,
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    decode_estop_word,
)

from .bindings import YellowBindings
from .ports import IntentOut, TelemetryIn

import logging
import time

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

        self._seen_first_telem = False
        self._last_rx_ns: int | None = None
        self._timer: QTimer | None = None

        
        if self.ui.btn_estop_reset is not None:
            self.ui.btn_estop_reset.clicked.connect(self._on_estop_reset)
            log.info("wired: btnEStopReset -> RequestEstopReset intent")
        else:
            log.warning("btnEStopReset not found in UI")

        if self.ui.btn_estop_reset:
            self.ui.btn_estop_reset.setEnabled(False)

        # paint all known dots as "unknown"
        self._set_all_estop_unknown()

    # ---------- LED helpers ----------

    def _set_led(self, w: QWidget | None, *, state: str | None) -> None:
        if w is None:
            return
        if w.property("state") != state:
            w.setProperty("state", state)
            w.style().unpolish(w)
            w.style().polish(w)
            w.update()

    def _set_led_by_name(self, object_name: str | None, *, state: str | None) -> None:
        if not object_name:
            return
        w = self.win.findChild(QWidget, object_name)
        self._set_led(w, state=state)

    def _set_all_estop_unknown(self) -> None:
        for spec in ESTOP_SPECS.values():
            if spec.dot:
                self._set_led_by_name(spec.dot, state="warn")

    def _mark_disconnected(self) -> None:
        if self._seen_first_telem:
            log.warning("telemetry stale/disconnected -> reverting E-Stop LEDs to UNKNOWN")
        self._seen_first_telem = False
        if self.ui.btn_estop_reset:
            self.ui.btn_estop_reset.setEnabled(False)
        self._set_all_estop_unknown()

    # ---------- intents ----------

    def _on_estop_reset(self) -> None:
        # NOTE: caller is gated by button enable; we still keep this simple.
        intent = RequestEstopReset()
        log.info("tx intent: %s", type(intent).__name__)
        self.intent_out.publish_intent(intent)

    # ---------- polling ----------

    def start_polling(self, *, period_ms: int = 50) -> None:
        t = QTimer(self.win)
        t.setInterval(period_ms)
        t.timeout.connect(self.poll_once)
        t.start()
        self._timer = t

    def poll_once(self) -> None:
        snaps = self.telemetry_in.drain_telemetry(limit=50)

        now_ns = time.monotonic_ns()

        if not snaps:
            # If we previously had telemetry but it stopped -> go UNKNOWN after timeout
            if self._last_rx_ns is not None:
                age_ms = (now_ns - self._last_rx_ns) / 1_000_000.0
                if age_ms >= float(self.stale_after_ms):
                    self._last_rx_ns = None
                    self._mark_disconnected()
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

        log.debug(
            "rx telemetry: tick=%s estop=%s fault=%s",
            getattr(snap, "tick", None),
            getattr(snap, "estop", None),
            getattr(snap, "fault", None),
        )

        self._render_estop(snap)

    # ---------- render logic ----------

    def _render_estop(self, snap: TelemetrySnapshot) -> None:
        word = int(getattr(snap, "estop_status_word", 0))
        logical = decode_estop_word(word)
        log.debug("render estop word=%s logical=%s", hex(word), logical)

        if self.ui.btn_estop_reset:
            self.ui.btn_estop_reset.setEnabled(True)

        for spec in ESTOP_SPECS.values():
            if not spec.dot:
                continue

            v = bool(logical.get(spec.key, False))

            if spec.key in ESTOP_CAUSE_KEYS:
                state = "bad" if v else "good"
            elif spec.key in ESTOP_OK_KEYS:
                state = "good" if v else "bad"
            else:
                state = "warn" if v else None

            self._set_led_by_name(spec.dot, state=state)