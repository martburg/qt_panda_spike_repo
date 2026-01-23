# src/steuerung3d/apps/yellow/controllers/densi_controller.py
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QWidget

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot

from steuerung3d.protocol.estop_bits import (
    ESTOP_SPECS,
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    iter_specs,
    decode_estop_word,
    encode_estop_word,
)

from .bindings import YellowBindings
from .ports import CommandIn, TelemetryOut

import logging


log = logging.getLogger("den_si")


@dataclass
class DenSiController:
    win: QWidget
    command_in: CommandIn
    telemetry_out: TelemetryOut
    axis_ids: list[str]
    dt_s: float = 0.01


    def __post_init__(self) -> None:
        self.ui = YellowBindings.from_window(self.win)

        # DEBUG: list which estop checkboxes are actually found
        from steuerung3d.protocol.estop_bits import iter_specs
        for spec in iter_specs():
            if not spec.checkbox:
                continue
            w = self.win.findChild(QCheckBox, spec.checkbox)
            log.info("estop checkbox %-16s key=%-10s found=%s", spec.checkbox, spec.key, bool(w))


        self.tb = Timebase(dt_s=self.dt_s)
        self.state = MachineState()
        for a in self.axis_ids:
            self.state.ensure_axis(a)

        self.device = SimDevice(plant=SimAxisPlant())
        self._last_cmd: CommandFrame | None = None

        # LOGICAL injected bits (invert handled by encode/decode)
        self._inj_bits = {k: False for k in ESTOP_SPECS.keys()}

        # safe defaults:
        for k in ESTOP_OK_KEYS:
            self._inj_bits[k] = True          # OK chain healthy

        for k in ESTOP_CAUSE_KEYS:
            self._inj_bits[k] = False         # no trip cause

        self._inj_estop_word = encode_estop_word(self._inj_bits)

        self._estop_latched = False
        self._safety_ok = True  # placeholder

        # buttons
        if self.ui.btn_estop_all_set is not None:
            self.ui.btn_estop_all_set.clicked.connect(self._set_inj_estop_all)
        if self.ui.btn_estop_all_clear is not None:
            self.ui.btn_estop_all_clear.clicked.connect(self._clear_inj_estop_all)

        # auto-wire ALL per-bit checkboxes that exist
        self._wire_all_estop_bit_checkboxes()

        # initial paint
        self._render_estop_word_to_ui(self._inj_estop_word)

    # ----- UI helpers -----
    def _apply_go_state(self) -> None:
        """Set injected bits to a stable 'GO' state (no flash)."""
        # default everything False
        for k in self._inj_bits.keys():
            self._inj_bits[k] = False

        # OK keys True (green)
        for k in ESTOP_OK_KEYS:
            self._inj_bits[k] = True

        # Cause keys False (green)
        for k in ESTOP_CAUSE_KEYS:
            self._inj_bits[k] = False

        self._inj_estop_word = encode_estop_word(self._inj_bits)
        self._estop_latched = False
        self._render_estop_word_to_ui(self._inj_estop_word)

    def _set_led_state_by_name(self, object_name: str | None, state: str | None) -> None:
        if not object_name:
            return
        w = self.win.findChild(QWidget, object_name)
        if w is None:
            return
        if w.property("state") == state:
            return
        w.setProperty("state", state)
        w.style().unpolish(w)
        w.style().polish(w)
        w.update()

    def _wire_all_estop_bit_checkboxes(self) -> None:
        for spec in iter_specs():
            if not spec.checkbox:
                continue

            cb = self.win.findChild(QCheckBox, spec.checkbox)
            if cb is None:
                # don't spam info; debug is enough
                log.debug("checkbox not found: %s (key=%s)", spec.checkbox, spec.key)
                continue

            # init checkbox from current word (logical values)
            current_bits = decode_estop_word(self._inj_estop_word)
            cb.setChecked(bool(current_bits.get(spec.key, False)))

            def _make_handler(key: str, checkbox_name: str):
                def _on_toggled(checked: bool) -> None:
                    self._inj_bits[key] = bool(checked)
                    self._inj_estop_word = encode_estop_word(self._inj_bits)
                    log.info("inject estop %s=%s (word=0x%08X)", key, checked, self._inj_estop_word)
                    self._render_estop_word_to_ui(self._inj_estop_word)
                return _on_toggled

            cb.toggled.connect(_make_handler(spec.key, spec.checkbox))
            log.info("wired: %s -> estop key '%s'", spec.checkbox, spec.key)

    def _render_estop_word_to_ui(self, word: int) -> None:
        bits = decode_estop_word(word)

        # sync checkboxes (avoid feedback loops)
        for spec in iter_specs():
            if not spec.checkbox:
                continue
            cb = self.win.findChild(QCheckBox, spec.checkbox)
            if cb is None:
                continue
            was = cb.blockSignals(True)
            cb.setChecked(bool(bits.get(spec.key, False)))
            cb.blockSignals(was)

        # sync dots/LEDs using 'state'
        for spec in iter_specs():
            if not spec.dot:
                continue

            v = bool(bits.get(spec.key, False))

            if spec.key in ESTOP_CAUSE_KEYS:
                # trip causes: show red when active, otherwise green
                state = "bad" if v else "good"

            elif spec.key in ESTOP_OK_KEYS:
                # ok chain: green when ok, red when broken
                state = "good" if v else "bad"

            else:
                # other: amber only when asserted, otherwise off
                state = "warn" if v else None

            self._set_led_state_by_name(spec.dot, state)

    # ----- diagnostic actions -----

    def _set_inj_estop_all(self) -> None:
        # Set ALL logical bits to True
        for k in self._inj_bits.keys():
            self._inj_bits[k] = True
        self._inj_estop_word = encode_estop_word(self._inj_bits)
        log.info("inject: SET ALL bits (word=0x%08X)", self._inj_estop_word)
        self._render_estop_word_to_ui(self._inj_estop_word)

    def _clear_inj_estop_all(self) -> None:
        # Clear ALL logical bits to False
        for k in self._inj_bits.keys():
            self._inj_bits[k] = False
        self._inj_estop_word = encode_estop_word(self._inj_bits)
        log.info("inject: CLEAR ALL bits (word=0x%08X)", self._inj_estop_word)
        self._render_estop_word_to_ui(self._inj_estop_word)

    # ----- runtime -----

    def start(self) -> None:
        t = QTimer(self.win)
        t.setInterval(int(self.dt_s * 1000))
        t.timeout.connect(self.step_once)
        t.start()
        self._timer = t

    def step_once(self) -> None:
        frames = self.command_in.drain_command_frames(limit=100)
        if frames:
            self._last_cmd = frames[-1]
            log.debug(
                "rx cmd: tick=%s estop_reset=%s fault=%s mode=%s",
                self._last_cmd.tick,
                getattr(self._last_cmd, "estop_reset", None),
                self._last_cmd.fault,
                self._last_cmd.mode,
            )

        if self._last_cmd is None:
            self._last_cmd = CommandFrame(
                tick=self.state.tick,
                t_s=self.state.t_s,
                estop=False,
                fault=False,
                mode=self.state.mode,
                axes={},
                estop_reset=False,
            )

        # Reset => GO state (no flash)
        if bool(getattr(self._last_cmd, "estop_reset", False)):
            log.info("estop_reset received -> GO state (no flash)")
            self._apply_go_state()

        estop_word = int(self._inj_estop_word)
        bits = decode_estop_word(estop_word)

        # trip only on actual "cause" bits (NOT on OK/status bits)
        trip = any(bool(bits.get(k, False)) for k in ESTOP_CAUSE_KEYS) or (not self._safety_ok)
        if trip:
            self._estop_latched = True

        self.state.estop = bool(self._estop_latched)
        self.state.estop_status_word = estop_word

        self.device.step(self.state, self._last_cmd, self.tb.dt_s)

        if self.state.estop:
            for ax in self.state.axes.values():
                ax.enabled = False
                ax.vel = 0.0

        self.state.tick += 1
        self.state.t_s += self.tb.dt_s

        snap = TelemetrySnapshot.from_state(self.state)
        self.telemetry_out.publish_telemetry(snap)

        log.debug(
            "tx telem: tick=%s estop=%s fault=%s estop_word=%s",
            snap.tick, snap.estop, snap.fault, hex(snap.estop_status_word),
        )
