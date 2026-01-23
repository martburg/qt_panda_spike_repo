# src/steuerung3d/apps/yellow/controllers/hip_controller.py
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QLocale, QTimer
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QLineEdit, QPushButton, QWidget

from steuerung3d.core.intents import ParamCancel, ParamEditBegin, ParamWrite, RequestEstopReset
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.estop_bits import (
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    ESTOP_SPECS,
    decode_estop_word,
)

from .bindings import YellowBindings
from .ports import IntentOut, TelemetryIn

import logging
import time

log = logging.getLogger("hi_p")


# v0.1 axis-agnostic parameter wiring (UI widget names -> param keys)
_PARAM_WIDGETS: dict[str, dict[str, str]] = {
    "pos": {
        "HardMax": "txtHardMax_2",
        "UserMax": "txtUserMax_2",
        "UserMin": "txtUserMin_2",
        "HardMin": "txtHardMin_2",
        "PosWin": "txtPosWin_2",
    },
    "vel": {
        "VelMax": "txtVelMax_3",
        "VelWin": "txtVelWin_3",
        "AccMax": "txtAccMax_3",
        "AccMove": "txtAccMove_3",
        "DccMax": "txtDccMax_3",
        "MaxAmp": "txtMaxAmp_3",
        "VelMaxMot": "txtVelMaxMot_3",
    },
    "filter": {
        "P": "txtP_2",
        "I": "txtI_2",
        "D": "txtD_2",
        "IL": "txtIL_2",
        "RampForm": "txtRamp_2",
    },
    "guider": {
        "PosMin": "txtGPosMin_2",
        "PosMax": "txtGPosMax_2",
    },
}


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

        # parameter buttons (axis-agnostic v0.1)
        self._wire_param_buttons()

        # Install numeric validators + mark param fields for QSS
        self._init_param_inputs()

        # Parameter UI starts locked until DenSi enters edit mode
        self._apply_param_ui_state(edit_active=False, edit_group="")

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
        intent = RequestEstopReset()
        log.info("tx intent: %s", type(intent).__name__)
        self.intent_out.publish_intent(intent)

    # ----- parameters (axis-agnostic v0.1) -----

    def _find_button(self, object_name: str) -> QPushButton | None:
        w = self.win.findChild(QPushButton, object_name)
        return w if isinstance(w, QPushButton) else None

    def _find_line_edit(self, object_name: str) -> QLineEdit | None:
        w = self.win.findChild(QLineEdit, object_name)
        return w if isinstance(w, QLineEdit) else None

    def _init_param_inputs(self) -> None:
        """Mark param fields for QSS + restrict input to numbers."""
        loc = QLocale.system()
        for _grp, mapping in _PARAM_WIDGETS.items():
            for _key, obj_name in mapping.items():
                le = self._find_line_edit(obj_name)
                if le is None:
                    continue
                # For QSS: enabled param fields should turn white on HiP.
                le.setProperty("paramField", True)
                # Numeric-only entry; parent the validator to the field so it stays alive.
                val = QDoubleValidator(-1.0e12, 1.0e12, 6, le)
                val.setLocale(loc)
                val.setNotation(QDoubleValidator.Notation.StandardNotation)
                le.setValidator(val)

    def _parse_float(self, s: str) -> float:
        s = (s or "").strip()
        if not s:
            return 0.0
        # Accept both decimal comma and dot.
        s = s.replace(",", ".")
        return float(s)

    def _read_param_values(self, group: str) -> dict[str, float]:
        mapping = _PARAM_WIDGETS.get(group, {})
        out: dict[str, float] = {}
        for key, obj_name in mapping.items():
            le = self._find_line_edit(obj_name)
            if le is None:
                continue
            try:
                out[key] = self._parse_float(le.text())
            except ValueError:
                log.warning("param parse failed: %s=%r", key, le.text())
        return out

    def _write_back_values(self, group: str, values: dict[str, float]) -> None:
        mapping = _PARAM_WIDGETS.get(group, {})
        for key, obj_name in mapping.items():
            if key not in values:
                continue
            le = self._find_line_edit(obj_name)
            if le is None:
                continue
            txt = f"{values[key]:g}"
            if le.text() == txt:
                continue
            was = le.blockSignals(True)
            le.setText(txt)
            le.blockSignals(was)

    def _normalize_pos_chain(self, values: dict[str, float]) -> dict[str, float]:
        """Enforce HardMax>=UserMax>=UserMin>=HardMin."""
        v = dict(values)
        need = {"HardMax", "UserMax", "UserMin", "HardMin"}
        if not need.issubset(v.keys()):
            return v

        hard_max = float(v["HardMax"])
        hard_min = float(v["HardMin"])
        user_max = float(v["UserMax"])
        user_min = float(v["UserMin"])

        if hard_max < hard_min:
            hard_max, hard_min = hard_min, hard_max

        # clamp into bounds
        user_max = max(min(user_max, hard_max), hard_min)
        user_min = max(min(user_min, user_max), hard_min)

        v["HardMax"] = hard_max
        v["HardMin"] = hard_min
        v["UserMax"] = user_max
        v["UserMin"] = user_min
        return v

    def _normalize_guider_range(self, values: dict[str, float]) -> dict[str, float]:
        """Enforce PosMin < PosMax for guider group."""
        v = dict(values)
        if "PosMin" not in v or "PosMax" not in v:
            return v

        pos_min = float(v["PosMin"])
        pos_max = float(v["PosMax"])

        if pos_min > pos_max:
            pos_min, pos_max = pos_max, pos_min
        if pos_min == pos_max:
            pos_max = pos_min + (1e-6 * (abs(pos_min) + 1.0))

        v["PosMin"] = pos_min
        v["PosMax"] = pos_max
        return v

    def _wire_param_buttons(self) -> None:
        wiring = {
            "pos": ("btnPosEdit", "btnPosWrite", "btnPosCancel"),
            "vel": ("btnVelEdit", "btnVelWrite", "btnVelCancel"),
            "filter": ("btnFilterEdit", "btnFilterWrite", "btnFilterCancel"),
            "guider": ("btnGuiderEdit", "btnGuiderWrite", "btnGuiderCancel"),
        }

        for grp, (b_edit, b_write, b_cancel) in wiring.items():
            be = self._find_button(b_edit)
            bw = self._find_button(b_write)
            bc = self._find_button(b_cancel)

            if be is not None:
                be.clicked.connect(lambda _=False, g=grp: self._tx_param_edit(g))
                log.info("wired: %s -> ParamEditBegin(group=%s)", b_edit, grp)
            else:
                log.debug("button not found: %s", b_edit)

            if bw is not None:
                bw.clicked.connect(lambda _=False, g=grp: self._tx_param_write(g))
                log.info("wired: %s -> ParamWrite(group=%s)", b_write, grp)
            else:
                log.debug("button not found: %s", b_write)

            if bc is not None:
                bc.clicked.connect(lambda _=False, g=grp: self._tx_param_cancel(g))
                log.info("wired: %s -> ParamCancel(group=%s)", b_cancel, grp)
            else:
                log.debug("button not found: %s", b_cancel)

    def _tx_param_edit(self, group: str) -> None:
        intent = ParamEditBegin(group=group)
        log.info("tx intent: %s group=%s", type(intent).__name__, group)
        self.intent_out.publish_intent(intent)

    def _tx_param_write(self, group: str) -> None:
        vals = self._read_param_values(group)

        # Guard constraints for known groups
        fixed = dict(vals)
        if group == "pos":
            fixed = self._normalize_pos_chain(fixed)
        elif group == "guider":
            fixed = self._normalize_guider_range(fixed)

        if fixed != vals:
            log.info("param guards adjusted %s values", group)
            self._write_back_values(group, fixed)

        intent = ParamWrite(group=group, values=fixed)
        log.info("tx intent: %s group=%s keys=%s", type(intent).__name__, group, sorted(fixed.keys()))
        self.intent_out.publish_intent(intent)

    def _tx_param_cancel(self, group: str) -> None:
        intent = ParamCancel(group=group)
        log.info("tx intent: %s group=%s", type(intent).__name__, group)
        self.intent_out.publish_intent(intent)

    # ----- parameters: UI state reflection (axis-agnostic v0.1) -----

    def _set_param_group_enabled(self, group: str, enabled: bool) -> None:
        """Enable/disable the parameter line-edits for a group."""
        mapping = _PARAM_WIDGETS.get(group, {})
        for _key, obj_name in mapping.items():
            le = self._find_line_edit(obj_name)
            if le is None:
                continue
            le.setEnabled(bool(enabled))

    def _set_param_button_state(self, group: str, *, editing: bool) -> None:
        wiring = {
            "pos": ("btnPosEdit", "btnPosWrite", "btnPosCancel"),
            "vel": ("btnVelEdit", "btnVelWrite", "btnVelCancel"),
            "filter": ("btnFilterEdit", "btnFilterWrite", "btnFilterCancel"),
            "guider": ("btnGuiderEdit", "btnGuiderWrite", "btnGuiderCancel"),
        }
        b_edit, b_write, b_cancel = wiring[group]
        be = self._find_button(b_edit)
        bw = self._find_button(b_write)
        bc = self._find_button(b_cancel)

        if be is not None:
            be.setEnabled(not editing)
        if bw is not None:
            bw.setEnabled(editing)
        if bc is not None:
            bc.setEnabled(editing)

    def _apply_param_ui_state(self, *, edit_active: bool, edit_group: str) -> None:
        """Reflect DenSi edit state onto HiP widget enable/disable."""
        groups = ("pos", "vel", "filter", "guider")
        if not edit_active:
            for g in groups:
                self._set_param_group_enabled(g, False)
                self._set_param_button_state(g, editing=False)
            return

        for g in groups:
            is_edit = (g == edit_group)
            self._set_param_group_enabled(g, is_edit)
            self._set_param_button_state(g, editing=is_edit)

    def _render_params_from_telemetry(
        self,
        snap: TelemetrySnapshot,
        *,
        skip_group: str | None = None,
    ) -> None:
        """Update parameter text fields from telemetry.

        UX rule: while DenSi is in edit mode for a group, we MUST NOT overwrite
        the user's in-progress edits with stale telemetry values.
        """
        params = getattr(snap, "params", None)
        if not isinstance(params, dict) or not params:
            return

        for grp, mapping in _PARAM_WIDGETS.items():
            if skip_group and grp == skip_group:
                continue

            for key, obj_name in mapping.items():
                if key not in params:
                    continue
                le = self._find_line_edit(obj_name)
                if le is None:
                    continue

                # Never overwrite a field the user is actively typing into.
                if le.hasFocus():
                    continue

                val = params[key]
                txt = f"{val:g}" if isinstance(val, (int, float)) else str(val)
                if le.text() == txt:
                    continue
                was = le.blockSignals(True)
                le.setText(txt)
                le.blockSignals(was)

    def _render_params_and_edit_state(self, snap: TelemetrySnapshot) -> None:
        edit_active = bool(getattr(snap, "param_edit_active", False))
        edit_group = str(getattr(snap, "param_edit_group", "") or "")

        # First reflect edit enable/disable, then update values for all *other* groups.
        self._apply_param_ui_state(edit_active=edit_active, edit_group=edit_group)
        self._render_params_from_telemetry(snap, skip_group=(edit_group if edit_active else None))

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
        self._render_params_and_edit_state(snap)

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
