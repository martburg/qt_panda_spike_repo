# src/steuerung3d/apps/yellow/controllers/densi_controller.py
from __future__ import annotations

from dataclasses import dataclass
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QWidget, QLineEdit, QComboBox

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

# --- Lifetick tracing (DenSi -> Core -> HiP -> Core -> DenSi) ---
# Keep logging useful (avoid per-tick spam): throttle to at most once per 0.5s.
_LT_LOG_EVERY_S = 0.5


def _lt_should_log(now_s: float, last_s: float) -> bool:
    return (now_s - last_s) >= _LT_LOG_EVERY_S


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
        "RampForm": "txtRamp_2",    },
    "guider": {
        "PosMax": "txtGPosMax_2",
        "PosMin": "txtGPosMin_3",
        "Pitch": "txtPitch_2",
    },
}

# Limit display fields in the header bar (meters)
_LIMIT_WIDGETS: dict[str, str] = {
    "HardMin": "txtLimitHardMin",
    "UserMin": "txtLimitUserMin",
    "UserMax": "txtLimitUserMax",
    "HardMax": "txtLimitHardMax",
}


@dataclass
class DenSiController:
    win: QWidget
    command_in: CommandIn
    telemetry_out: TelemetryOut
    axis_ids: list[str]
    dt_s: float = 0.01


    def __post_init__(self) -> None:
        self.ui = YellowBindings.from_window(self.win)

        # Legacy TimeTick display on device side:
        # show (lifetick_tx - lifetick_rx) in milliseconds (WORD wrap).
        self._txt_tick: QLineEdit | None = self.win.findChild(QLineEdit, "txt_tick")

        # DenSi is normally bound to exactly one axis. To reduce confusion during
        # multi-window integration, show the axis name directly in cmb_axis.
        cmb = self.win.findChild(QComboBox, "cmb_axis")
        if cmb is not None:
            label = self.axis_ids[0] if self.axis_ids else "?"
            try:
                was = cmb.blockSignals(True)
                cmb.clear()
                cmb.addItems([label])
                cmb.setCurrentText(label)
                cmb.setEnabled(False)
                cmb.blockSignals(was)
            except Exception:
                pass

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

        # initialize parameter bank from current UI text (if present)
        self._seed_params_from_ui()

        # Render limit header fields (txtLimit*) from seeded params.
        self._render_limit_fields_from_params(self.state.params)

        self.device = SimDevice(plant=SimAxisPlant())
        self._last_cmd: CommandFrame | None = None

        # Lifetick tracing / log throttling
        self._lt_last_telem_log_s: float = 0.0
        self._lt_last_cmd_log_s: float = 0.0
        # last echoed lifetick seen in cmd frames (per axis)
        self._lt_last_echo_by_axis: dict[str, int | None] = {}

        # LOGICAL injected bits (invert handled by encode/decode)
        self._inj_bits = {k: False for k in ESTOP_SPECS.keys()}

        # safe defaults:
        for k in ESTOP_OK_KEYS:
            self._inj_bits[k] = False          # OK chain healthy

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

        # DenSi is the remote endpoint: parameter edit/write/cancel is driven from HiP
        self._disable_param_edit_buttons()
        self._disable_param_fields()

        # Reset device-side tick display
        if self._txt_tick is not None:
            self._txt_tick.setText("--")

    def _seed_params_from_ui(self) -> None:
        for _grp, mapping in _PARAM_WIDGETS.items():
            for key, wname in mapping.items():
                w = self.win.findChild(QLineEdit, wname)
                if w is None:
                    continue
                try:
                    self.state.params[key] = float(w.text())
                except Exception:
                    # keep missing/invalid as-is
                    continue

    def _ui_set_param(self, key: str, value: float) -> None:
        # Update UI field if we know its widget name.
        for _grp, mapping in _PARAM_WIDGETS.items():
            wname = mapping.get(key)
            if not wname:
                continue
            w = self.win.findChild(QLineEdit, wname)
            if w is None:
                continue
            # avoid unnecessary signal churn
            txt = f"{value:g}"
            if w.text() == txt:
                return
            was = w.blockSignals(True)
            w.setText(txt)
            w.blockSignals(was)
            return

    def _disable_param_edit_buttons(self) -> None:
        """Disable parameter Edit/Write/Cancel buttons on DenSi UI.

        DenSi is the device side; operators should not change parameters locally.
        """
        from PySide6.QtWidgets import QPushButton

        btn_names = [
            'btnPosEdit','btnPosWrite','btnPosCancel',
            'btnVelEdit','btnVelWrite','btnVelCancel',
            'btnFilterEdit','btnFilterWrite','btnFilterCancel',
            'btnGuiderEdit','btnGuiderWrite','btnGuiderCancel',
        ]
        for name in btn_names:
            b = self.win.findChild(QPushButton, name)
            if b is not None:
                b.setEnabled(False)

    def _disable_param_fields(self) -> None:
        """Disable parameter line edits on DenSi UI (device side).

        They remain updated programmatically, but appear grey/locked.
        """
        for _grp, mapping in _PARAM_WIDGETS.items():
            for _key, wname in mapping.items():
                le = self.win.findChild(QLineEdit, wname)
                if le is None:
                    continue
                # Mark for QSS (even though we disable them)
                if le.property('paramField') is None:
                    # QSS selector uses string: paramField="true"
                    le.setProperty('paramField', 'true')
                    le.style().unpolish(le)
                    le.style().polish(le)
                le.setEnabled(False)

    def _enforce_pos_chain(self, vals: dict[str, float]) -> dict[str, float]:
        """Enforce HardMax>=UserMax>=UserMin>=HardMin."""
        v = dict(vals)
        need = ('HardMax','UserMax','UserMin','HardMin')
        if not all(k in v for k in need):
            return v
        hard_max = float(v['HardMax']); hard_min = float(v['HardMin'])
        user_max = float(v['UserMax']); user_min = float(v['UserMin'])
        if hard_max < hard_min:
            hard_max, hard_min = hard_min, hard_max
        user_max = max(hard_min, min(hard_max, user_max))
        user_min = max(hard_min, min(user_max, user_min))
        v['HardMax']=hard_max; v['HardMin']=hard_min; v['UserMax']=user_max; v['UserMin']=user_min
        return v

    def _enforce_guider_minmax(self, vals: dict[str, float]) -> dict[str, float]:
        """Enforce PosMin < PosMax."""
        v = dict(vals)
        if 'PosMin' not in v or 'PosMax' not in v:
            return v
        pos_min = float(v['PosMin']); pos_max = float(v['PosMax'])
        if pos_min > pos_max:
            pos_min, pos_max = pos_max, pos_min
        if pos_min == pos_max:
            pos_max = pos_min + (1e-6 * (abs(pos_min) + 1.0))
        v['PosMin']=pos_min; v['PosMax']=pos_max
        return v

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

    # ----- parameter helpers -----
    def _find_line_edit(self, object_name: str) -> QLineEdit | None:
        w = self.win.findChild(QLineEdit, object_name)
        return w if isinstance(w, QLineEdit) else None

    def _seed_params_from_ui(self) -> None:
        """Populate state.params from UI fields if available.

        This makes DenSi a useful echo-target for HiP parameter writes.
        """
        params: dict[str, float] = {}
        for _grp, mapping in _PARAM_WIDGETS.items():
            for key, obj_name in mapping.items():
                le = self._find_line_edit(obj_name)
                if le is None:
                    continue
                try:
                    params[key] = float(le.text().strip() or "0")
                except ValueError:
                    continue
        self.state.params = params

    def _apply_param_values_to_ui(self, values: dict[str, float]) -> None:
        # Push updated values to any known widgets.
        for _grp, mapping in _PARAM_WIDGETS.items():
            for key, obj_name in mapping.items():
                if key not in values:
                    continue
                le = self._find_line_edit(obj_name)
                if le is None:
                    continue
                le.setText(str(values[key]))

        # Also update the compact header limit fields if those values are present.
        self._render_limit_fields_from_params(values)

    def _fmt_m(self, v: float) -> str:
        """Format a length in meters for the compact limit fields."""
        try:
            s = f"{float(v):0.2f} m"
        except Exception:
            s = ""
        # Use comma as decimal separator (more natural for our locale).
        return s.replace(".", ",")

    def _render_limit_fields_from_params(self, values: dict[str, float]) -> None:
        """Update txtLimitHardMin/UserMin/UserMax/HardMax from parameter values."""
        for key, obj_name in _LIMIT_WIDGETS.items():
            if key not in values:
                continue
            le = self._find_line_edit(obj_name)
            if le is None:
                continue
            txt = self._fmt_m(values[key])
            if le.text() == txt:
                continue
            was = le.blockSignals(True)
            le.setText(txt)
            le.blockSignals(was)
            # Ensure these are display-only on DenSi.
            try:
                le.setEnabled(False)
            except Exception:
                pass

    def _normalize_pos_chain(self, values: dict[str, float]) -> dict[str, float]:
        v = dict(values)
        keys = ('HardMax', 'UserMax', 'UserMin', 'HardMin')
        if not all(k in v for k in keys):
            return v

        hard_max = float(v['HardMax'])
        user_max = float(v['UserMax'])
        user_min = float(v['UserMin'])
        hard_min = float(v['HardMin'])

        if hard_max < hard_min:
            hard_max, hard_min = hard_min, hard_max

        user_max = max(hard_min, min(hard_max, user_max))
        user_min = max(hard_min, min(user_max, user_min))

        v['HardMax'] = hard_max
        v['HardMin'] = hard_min
        v['UserMax'] = user_max
        v['UserMin'] = user_min
        return v

    def _normalize_guider_range(self, values: dict[str, float]) -> dict[str, float]:
        v = dict(values)
        if 'PosMin' not in v or 'PosMax' not in v:
            return v
        pos_min = float(v['PosMin'])
        pos_max = float(v['PosMax'])
        if pos_min > pos_max:
            pos_min, pos_max = pos_max, pos_min
        if pos_min == pos_max:
            pos_max = pos_min + (1e-6 * (abs(pos_min) + 1.0))
        v['PosMin'] = pos_min
        v['PosMax'] = pos_max
        return v

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

        # ----- parameter ops (axis-agnostic v0.1) -----
        for op in list(getattr(self._last_cmd, "param_ops", []) or []):
            try:
                op_type = getattr(op, "type", None) or (op.get("type") if isinstance(op, dict) else None)
            except Exception:
                op_type = None

            if op_type == "param_edit_begin":
                grp = getattr(op, "group", "") or (op.get("group") if isinstance(op, dict) else "")
                self.state.param_edit_active = True
                self.state.param_edit_group = str(grp)
                log.info("param_edit_begin: group=%s", grp)

            elif op_type == "param_cancel":
                grp = getattr(op, "group", "") or (op.get("group") if isinstance(op, dict) else "")
                if (not grp) or (str(grp) == self.state.param_edit_group):
                    self.state.param_edit_active = False
                    self.state.param_edit_group = ""
                log.info("param_cancel: group=%s", grp)

            elif op_type == "param_write":
                grp = getattr(op, "group", "") or (op.get("group") if isinstance(op, dict) else "")
                vals = getattr(op, "values", None) or (op.get("values") if isinstance(op, dict) else {})
                vals = {str(k): float(v) for k, v in dict(vals).items()}

                # Simple policy: only accept if group matches current edit group.

                # enforce minimal device-side guards too
                if str(grp) == 'pos':
                    vals = self._normalize_pos_chain(vals)
                elif str(grp) == 'guider':
                    vals = self._normalize_guider_range(vals)
                if (not self.state.param_edit_active) or (str(grp) != self.state.param_edit_group):
                    log.warning(
                        "param_write rejected: group=%s active=%s active_group=%s",
                        grp,
                        self.state.param_edit_active,
                        self.state.param_edit_group,
                    )
                else:
                    if str(grp) == 'pos':
                        vals = self._enforce_pos_chain(vals)
                    elif str(grp) == 'guider':
                        vals = self._enforce_guider_minmax(vals)

                    self.state.params.update(vals)
                    self._apply_param_values_to_ui(vals)
                    # end edit session after a successful write
                    self.state.param_edit_active = False
                    self.state.param_edit_group = ""
                    log.info("param_write accepted: group=%s keys=%s", grp, sorted(vals.keys()))

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

        # --- LiveTick semantics (device-origin) ---
        # tx: incrementing device tick (DenSi sim, ms-based 16-bit counter)
        # rx: echo value received from HiP/Core in last command frame
        now_s = time.monotonic()
        _echo_map = getattr(self._last_cmd, "lifetick_echo", {}) if self._last_cmd is not None else {}

        # LIFETICK (core -> DenSi): log echo changes immediately; otherwise throttle.
        if self._last_cmd is not None and self.axis_ids:
            for axis_id in self.axis_ids:
                echo_val = dict(_echo_map).get(axis_id, None)
                prev = self._lt_last_echo_by_axis.get(axis_id)
                if prev != echo_val:
                    self._lt_last_echo_by_axis[axis_id] = echo_val
                    log.info(
                        "LIFETICK DenSi rx cmd echo: axis=%s value=%s cmd_tick=%s",
                        axis_id,
                        echo_val,
                        getattr(self._last_cmd, "tick", None),
                    )

            if _lt_should_log(now_s, self._lt_last_cmd_log_s):
                axis0 = self.axis_ids[0]
                log.debug(
                    "DenSi rx cmd: tick=%s lifetick_echo[%s]=%s (map=%s)",
                    getattr(self._last_cmd, "tick", None),
                    axis0,
                    dict(_echo_map).get(axis0, None),
                    _echo_map,
                )
                self._lt_last_cmd_log_s = now_s
        else:
            if _lt_should_log(now_s, self._lt_last_cmd_log_s):
                log.debug("DenSi rx cmd: <no cmd yet>")
                self._lt_last_cmd_log_s = now_s

        inc_ms = max(1, int(round(self.tb.dt_s * 1000.0)))
        for _axis_id, _ax in self.state.axes.items():
            # Legacy PLC analogue: LifetickUItx is a WORD that increments in (roughly) milliseconds.
            # This drives the GUI's TimeTick display (delta between successive received lifeticks).
            prev = int(_ax.meta.get("device_tick", 0)) & 0xFFFF
            dev_tick = (prev + inc_ms) & 0xFFFF
            _ax.meta["device_tick"] = dev_tick

            # Keep livetick_tx aligned with device_tick for echo/watchdog semantics.
            _ax.meta["lifetick_tx"] = int(dev_tick)           
            try:
                _ax.meta["lifetick_rx"] = int(dict(_echo_map).get(_axis_id, 0) or 0)
            except Exception:
                _ax.meta["lifetick_rx"] = 0
            # Cycle time indicator for debugging/UX.
            _ax.meta["timetick_ms"] = inc_ms

            # Debug log the tick values
            tx = int(_ax.meta.get("lifetick_tx", 0)) & 0xFFFF
            rx = int(_ax.meta.get("lifetick_rx", 0)) & 0xFFFF
            diff = (tx - rx) & 0xFFFF

            # LIFETICK trace (throttled): DenSi -> Core (tx) and Core/HiP -> DenSi (rx echo)
            if self.axis_ids and _axis_id == self.axis_ids[0] and _lt_should_log(now_s, self._lt_last_telem_log_s):
                self._lt_last_telem_log_s = now_s
                log.info(
                    "LIFETICK DenSi device: axis=%s tx=%d rx=%d diff=%d",
                    _axis_id,
                    tx,
                    rx,
                    diff,
                )

        # Render device-side tick staleness like PLC does:
        # diff = LifetickUItx - LifetickUIrx (WORD wrap)
        if self._txt_tick is not None and self.axis_ids:
            axis_id = self.axis_ids[0]
            ax = self.state.axes.get(axis_id)
            if ax is not None:
                try:
                    tx = int(ax.meta.get("lifetick_tx", 0)) & 0xFFFF
                except Exception:
                    tx = 0
                try:
                    rx = int(ax.meta.get("lifetick_rx", 0)) & 0xFFFF
                except Exception:
                    rx = 0
                diff = (tx - rx) & 0xFFFF
                # avoid repaint churn
                s = str(diff)
                if self._txt_tick.text() != s:
                    self._txt_tick.setText(s)
            else:
                if self._txt_tick.text() != "--":
                    self._txt_tick.setText("--")

        snap = TelemetrySnapshot.from_state(self.state)
        self.telemetry_out.publish_telemetry(snap)

        log.debug("device_tick=%s", self.state.axes[next(iter(self.state.axes))].meta.get("device_tick"))

        log.debug(
            "tx telem: tick=%s estop=%s fault=%s estop_word=%s",
            snap.tick, snap.estop, snap.fault, hex(snap.estop_status_word),
        )
