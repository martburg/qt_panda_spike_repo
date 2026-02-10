# src/steuerung3d/apps/yellow/controllers/densi_controller.py
from __future__ import annotations

from dataclasses import dataclass, replace
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QAbstractSlider, QCheckBox, QWidget, QLineEdit, QComboBox, QPushButton

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import CommandFrame, AxisSetpoint
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot

from steuerung3d.util.heartbeat import Heartbeat, ChangeTracker

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter  # type: ignore
except Exception:  # pragma: no cover
    StatusEmitter = None  # type: ignore

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
    # --- dataclass fields (MUST be here, at class scope) ---
    win: QWidget
    command_in: CommandIn
    telemetry_out: TelemetryOut
    axis_ids: list[str]

    wire_proto: str = "json"  # json|plc
    dt_s: float = 0.01
    stale_after_ms: int = 500

    def _drain_command_frames_compat(self, limit: int = 100):
        """Drain command frames from either JSON channels or PLC wire channels."""
        cin = self.command_in

        fn = getattr(cin, "drain_command_frames", None)
        if callable(fn):
            return fn(limit=limit)

        fn = getattr(cin, "drain", None)
        if callable(fn):
            return fn(limit=limit)

        out = []
        fn = getattr(cin, "recv_nowait", None)
        if callable(fn):
            for _ in range(limit):
                msg = fn()
                if msg is None:
                    break
                out.append(msg)
            return out

        fn = getattr(cin, "recv", None)
        if callable(fn):
            for _ in range(limit):
                msg = fn(timeout=0)
                if msg is None:
                    break
                out.append(msg)
            return out

        if hasattr(cin, "drain_lines"):
            list(cin.drain_lines(limit=limit))
            return []

        raise AttributeError(f"CommandIn does not support draining: {type(cin).__name__}")

    def _publish_telemetry_compat(self, payload) -> None:
        """Publish telemetry via either JSON channels or PLC wire channels."""
        out = self.telemetry_out

        if getattr(self, "wire_proto", "json") == "plc":
            # Prefer the PLC wire TelemetryOut implementation if available.
            # UdpPlcTelemetryOut.publish_telemetry() encodes via protocol.plc_wire.encode_plc_telemetry()
            if hasattr(out, "publish_telemetry"):
                out.publish_telemetry(payload)
                return

            # Fallback: encode a canonical ST-compatible uplink line and send it.
            from steuerung3d.protocol.plc_wire import encode_plc_telemetry

            line = encode_plc_telemetry(payload)

            if hasattr(out, "publish_line"):
                out.publish_line(line)
                return

            link = getattr(out, "link", None)
            if link is not None and hasattr(link, "send"):
                link.send(line.encode("utf-8"))
                return

            raise AttributeError(
                f"TelemetryOut does not support PLC uplink sending: {type(out).__name__}"
            )


        if hasattr(out, "publish_telemetry"):
            out.publish_telemetry(payload)
            return

        link = getattr(out, "link", None)
        if link is not None and hasattr(link, "send"):
            try:
                from steuerung3d.protocol.serde_telemetry import encode_telemetry
                data = encode_telemetry(payload)
            except Exception:
                data = (repr(payload) + "\n").encode("utf-8")
            link.send(data)
            return

        raise AttributeError(f"TelemetryOut does not support publishing: {type(out).__name__}")

    def __post_init__(self) -> None:
        # Normalize wire protocol selection
        self.wire_proto = (getattr(self, 'wire_proto', 'json') or 'json').strip().lower()
        self.ui = YellowBindings.from_window(self.win)

        # Logging helpers (1 Hz heartbeat + edge logs)
        self._hb = Heartbeat("den_si", interval_s=1.0)
        self._ch = ChangeTracker()
        self._last_cmd_ns: int | None = None

        # Structured status heartbeat (side-channel for supervisor birds-eye; PLC packets unchanged)
        self._status = StatusEmitter.from_env(default_service="den_si") if StatusEmitter else None
        self._last_mode: str = ""
        self._last_estop: bool = False
        self._last_fault: bool = False

        # Legacy TimeTick display on device side:
        # show (lifetick_tx - lifetick_rx) in milliseconds (WORD wrap).
        self._txt_tick: QLineEdit | None = self.win.findChild(QLineEdit, "txt_tick")

        # Live readouts on device page (position/velocity/current/temp)
        self._txt_pos: QLineEdit | None = self.win.findChild(QLineEdit, "txt_pos")
        self._txt_vel: QLineEdit | None = self.win.findChild(QLineEdit, "txt_vel")
        self._txt_amp: QLineEdit | None = self.win.findChild(QLineEdit, "txt_amp")
        self._txt_temp: QLineEdit | None = self.win.findChild(QLineEdit, "txt_temp")

        # Cut markers / diagnostics readouts (line edits on the UI)
        self._txt_cut_pos: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_pos")
        self._txt_cut_vel: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_vel")
        self._txt_cut_time: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_time")
        self._txt_posdiff: QLineEdit | None = self.win.findChild(QLineEdit, "txt_posdiff")

        # Resync clears cut markers (operator action after E-Stop / re-sync)
        self._btn_diag_resync: QPushButton | None = (self.win.findChild(QPushButton, "btnReSync")
            or self.win.findChild(QPushButton, "btnReSync")
            or self.win.findChild(QPushButton, "btnDiagResync"))
        if self._btn_diag_resync is not None:
            self._btn_diag_resync.clicked.connect(self._on_diag_resync_clicked)

        # Guider readouts (range min/max/value and measured guider speed)
        self._txt_guider_range_min: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeMin")
        self._txt_guider_range_max: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeMax")
        # Note: user typo sometimes "Ranfe"; actual UI name is txtGuiderRangeValue
        self._txt_guider_range_val: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeValue")
        # Renamed from txtGuiderPos_2 -> txtGuiderSpeed
        self._txt_guider_speed: QLineEdit | None = (
            self.win.findChild(QLineEdit, "txtGuiderSpeed")
            or self.win.findChild(QLineEdit, "txtGuiderPos_2")
        )



        # Sliders used as live indicators
        self._sld_vel_cmd: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldVelCmd")
        self._sld_limit_range: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldLimitRange")

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

        # Plausible measured defaults so UI/HiP have stable values from tick 0
        self.state.params.setdefault("ActCur", 0.0)  # A
        self.state.params.setdefault("Temp", 20.0)   # °C
        self.state.params.setdefault("CutPos", 0.0)  # m
        self.state.params.setdefault("CutVel", 0.0)  # m/s

        # Plausible guider defaults (so HiP and DenSi show sane numbers from tick 0)
        # Note: PosMin/PosMax are guider range limits in the legacy UI.
        self.state.params.setdefault("PosMin", 0.0)       # m
        self.state.params.setdefault("PosMax", 0.966)     # m
        self.state.params.setdefault("GuidePosIst", 0.011)    # m
        self.state.params.setdefault("GuideIstSpeed", 0.0)    # m/s


        # Render limit header fields (txtLimit*) from seeded params.
        self._render_limit_fields_from_params(self.state.params)

        self.device = SimDevice(plant=SimAxisPlant())
        self._last_cmd: CommandFrame | None = None

        # Online heuristics: DenSi is considered "online" once we've seen at least one
        # command frame from Core/HiP recently.
        self._seen_first_cmd: bool = False

        # Lifetick tracing / log throttling
        self._lt_last_telem_log_s: float = 0.0
        self._lt_last_cmd_log_s: float = 0.0
        # last echoed lifetick seen in cmd frames (per axis)
        self._lt_last_echo_by_axis: dict[str, int | None] = {}

        # LOGICAL injected bits (invert handled by encode/decode)
        self._inj_bits = {k: False for k in ESTOP_SPECS.keys()}

        # --- Startup / SafetyPLC handoff emulation ---
        # Real-world flow (simplified): EStop reset -> operator presses Taster -> after a short delay
        # the drives energize and brakes lift. We emulate that here so HiP sees plausible timing.
        self._taster_prev: bool = False
        self._taster_rise_t_s: float | None = None
        self._taster_delay_s: float = 2.0
        self._drive_ready: bool = False
        self._brake_override: bool = False  # set True if operator overrides BRK1/2 via checkboxes

        # --- Cut markers (latched on E-Stop entry) ---
        self._cut_valid: bool = False
        self._cut_pos_m: float = 0.0
        self._cut_vel_mps: float = 0.0
        self._cut_time_s: float = 0.0
        self._prev_estop_state: bool = False


        # Match HiP brake-dot display semantics (equivalence + SafetyPLC grace)
        self._BRAKE_HANDOFF_GRACE_S: float = 3.0
        self._taster_prev_disp: bool = False
        self._taster_pressed_s: float | None = None



        # Start in a "FAULT" state: show the full estop chain as broken until the operator
        # explicitly issues an E-Stop reset from HiP. Keep reset_able True so the reset
        # button is available immediately.
        self._apply_fault_state()

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

    def _apply_fault_state(self) -> None:
        """Set injected bits to an initial 'FAULT' state.

        Intent: when DenSi starts, HiP should immediately see a broken E-Stop/status
        chain and the operator's first action should be issuing an E-Stop reset.

        Policy:
          - Trip-causes asserted (red): ESTOP_CAUSE_KEYS => True
          - Status/OK chain broken (red): ESTOP_OK_KEYS => False
          - Allow reset immediately: reset_able => True
          - Other bits default False (off / warn only when asserted)
        """
        # default everything False
        for k in self._inj_bits.keys():
            self._inj_bits[k] = False

        # Trip causes asserted (red)
        for k in ESTOP_CAUSE_KEYS:
            self._inj_bits[k] = True

        # Break the OK chain (red)
        for k in ESTOP_OK_KEYS:
            self._inj_bits[k] = False

        # But allow reset right away
        self._inj_bits["reset_able"] = True

        self._inj_estop_word = encode_estop_word(self._inj_bits)
        self._estop_latched = True  # reflect 'trip' immediately in state.estop
        self._brake_override = False
        self._render_estop_word_to_ui(self._inj_estop_word)

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


    def _apply_post_reset_state(self) -> None:
        """Clear initial FAULT latch, but remain not-ready until Taster + delay."""
        # Start from a clean slate
        for k in self._inj_bits.keys():
            self._inj_bits[k] = False

        # OK keys True (green), cause keys False (green)
        for k in ESTOP_OK_KEYS:
            self._inj_bits[k] = True
        for k in ESTOP_CAUSE_KEYS:
            self._inj_bits[k] = False

        # Post-reset we are *not* yet ready: operator must press the Taster and wait a bit.
        for k in ("ready", "taster", "schuetz", "brk1_ok", "brk2_ok"):
            if k in self._inj_bits:
                self._inj_bits[k] = False

        # Reset should no longer be "available" once we've just consumed it (mimics PLC behavior).
        if "reset_able" in self._inj_bits:
            self._inj_bits["reset_able"] = False

        self._inj_estop_word = encode_estop_word(self._inj_bits)
        self._estop_latched = False

        # Reset startup timers/derived readiness
        self._taster_prev = False
        self._taster_rise_t_s = None
        self._drive_ready = False
        self._brake_override = False

        self._render_estop_word_to_ui(self._inj_estop_word)

    def _apply_startup_logic(self) -> None:
        """Emulate SafetyPLC timing: Taster -> (delay) -> drives ready & brakes lifted."""
        bits = self._inj_bits
        changed = False

        # If the E-Stop chain is tripped/latching, never progress into READY.
        trip_causes = any(bool(bits.get(k, False)) for k in ESTOP_CAUSE_KEYS)
        if trip_causes or self._estop_latched:
            if self._drive_ready:
                log.info("startup: inhibit (trip/latched) -> drive_ready=False")
            self._drive_ready = False
            self._taster_rise_t_s = None
            # force derived bits to a safe state
            for k in ("ready", "schuetz", "brk1_ok", "brk2_ok"):
                if bool(bits.get(k, False)):
                    bits[k] = False
                    changed = True
            self._taster_prev = bool(bits.get("taster", False))
            if changed:
                self._inj_estop_word = encode_estop_word(bits)
                self._render_estop_word_to_ui(self._inj_estop_word)
            return

        taster = bool(bits.get("taster", False))

        # Track rising edge
        if taster and (not self._taster_prev):
            self._taster_rise_t_s = float(self.state.t_s)
            log.info("startup: taster pressed -> arming timer started")
        elif not taster:
            if self._taster_prev:
                log.info("startup: taster released -> brakes engage")
            self._taster_rise_t_s = None

        armed = False
        if taster and (self._taster_rise_t_s is not None):
            armed = (float(self.state.t_s) - float(self._taster_rise_t_s)) >= float(self._taster_delay_s)

        # Derived outputs
        desired_ready = bool(armed)
        desired_brk_ok = bool(armed)  # raw brake bits represent "brakes lifted"
        desired_schuetz = bool(armed)

        if self._drive_ready != bool(armed):
            log.info("startup: drive_ready=%s", bool(armed))
        self._drive_ready = bool(armed)

        # READY + Schuetz are always driven by timing logic.
        for k, val in (
            ("ready", desired_ready),
            ("schuetz", desired_schuetz),
        ):
            if k in bits and bool(bits.get(k, False)) != bool(val):
                bits[k] = bool(val)
                changed = True

        # If operator previously overrode BRK1/BRK2, automatically return to auto-mode
        # once both raw brake bits match what the timing logic would set.
        if bool(getattr(self, "_brake_override", False)):
            b1 = bool(bits.get("brk1_ok", False))
            b2 = bool(bits.get("brk2_ok", False))
            if (b1 == bool(desired_brk_ok)) and (b2 == bool(desired_brk_ok)):
                self._brake_override = False

        # BRK1/BRK2 represent "brake lifted" state. Normally driven by timing logic,
        # but allow operator override from the diagnostic checkboxes.
        if not bool(getattr(self, "_brake_override", False)):
            for k in ("brk1_ok", "brk2_ok"):
                if k in bits and bool(bits.get(k, False)) != bool(desired_brk_ok):
                    bits[k] = bool(desired_brk_ok)
                    changed = True

        self._taster_prev = taster

        if changed:
            self._inj_estop_word = encode_estop_word(bits)
            self._render_estop_word_to_ui(self._inj_estop_word)

    @staticmethod
    def _make_drive_status_word(
        *,
        output_powered: bool,
        amp_ready: bool,
        referenced: bool,
        in_position: bool,
        brake_lifted: bool,
        fault: bool,
        zustand: int,
    ) -> int:
        w = 0
        if output_powered:
            w |= 1 << 0
        if amp_ready:
            w |= 1 << 1
        if referenced:
            w |= 1 << 2
        if in_position:
            w |= 1 << 3
        if brake_lifted:
            w |= 1 << 4
        if fault:
            w |= 1 << 5
        w |= (int(zustand) & 0xFF) << 8
        return int(w)

    def _update_drive_status_words(self) -> None:
        """Populate legacy Status/GuideStatus words so HiP can render AmpStatus lines."""
        # These words are part of the PLC uplink in the legacy protocol; the HiP decodes them
        # with protocol.drive_status.decode_drive_status().
        bits = decode_estop_word(int(self._inj_estop_word))
        taster = bool(bits.get("taster", False))

        for axis_id, ax in self.state.axes.items():
            vel = float(getattr(ax, "vel", 0.0) or 0.0)
            in_pos = abs(vel) < 1e-3

            if bool(self.state.estop):
                # Faulted / tripped
                main = self._make_drive_status_word(
                    output_powered=False, amp_ready=False, referenced=False, in_position=False,
                    brake_lifted=False, fault=True, zustand=14,
                )
                slave = self._make_drive_status_word(
                    output_powered=False, amp_ready=False, referenced=False, in_position=False,
                    brake_lifted=False, fault=True, zustand=14,
                )
            elif self._drive_ready and taster:
                # Normal ready state (post-taster delay): powered, ready, brakes lifted
                main = self._make_drive_status_word(
                    output_powered=True, amp_ready=True, referenced=True, in_position=in_pos,
                    brake_lifted=True, fault=False, zustand=10,
                )
                # Slave/guider typically reports a different zustand; keep it distinct.
                slave = self._make_drive_status_word(
                    output_powered=True, amp_ready=True, referenced=True, in_position=in_pos,
                    brake_lifted=True, fault=False, zustand=5,
                )
            else:
                # Post-reset but not yet armed: brakes on, not powered
                main = self._make_drive_status_word(
                    output_powered=False, amp_ready=False, referenced=False, in_position=False,
                    brake_lifted=False, fault=False, zustand=0,
                )
                slave = self._make_drive_status_word(
                    output_powered=False, amp_ready=False, referenced=False, in_position=False,
                    brake_lifted=False, fault=False, zustand=0,
                )

            ax.meta["status_word"] = int(main)
            ax.meta["guide_status_word"] = int(slave)

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

    def _render_header_online_dot(self) -> None:
        """Drive the header 'Online' dot (dotHdrOnline).

        On the DenSi side we don't have a drive status-word like HiP.
        Instead we treat the device as 'online' once it is actively
        receiving command frames from Core/HiP.
        """

        if not self._seen_first_cmd:
            self._set_led_state_by_name("dotHdrOnline", None)
            return

        now_ns = time.monotonic_ns()
        last_ns = self._last_cmd_ns or 0
        age_s = (now_ns - last_ns) / 1e9 if last_ns else 1e9

        # Green while frames are flowing, amber when stale.
        # (Tune threshold as needed; 1s is a good first cut for dt=10ms.)
        state = "good" if age_s <= 1.0 else "warn"
        self._set_led_state_by_name("dotHdrOnline", state)

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
                    # User-driven diagnostic override: if operator touches BRK1/BRK2, stop auto-forcing
                    # them from the Taster timing logic until the next reset cycle.
                    if key in ("brk1_ok", "brk2_ok"):
                        setattr(self, "_brake_override", True)

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
        taster = bool(bits.get("taster", False))
        self._update_taster_edge_disp(taster)

        for spec in iter_specs():
            if not spec.dot:
                continue

            v = bool(bits.get(spec.key, False))

            if spec.key in ("brk1_ok", "brk2_ok"):
                # Match HiP display semantics for brake dots
                disp_ok = self._brake_ok_display_disp(brk_ok_raw=v, taster=taster)
                state = "good" if disp_ok else "bad"

            elif spec.key == "brk2kb_ok":
                # Brake cable OK: normal logic, independent of taster
                state = "good" if v else "bad"

            elif spec.key in ESTOP_CAUSE_KEYS:
                # trip causes: show red when active, otherwise green
                state = "bad" if v else "good"

            elif spec.key in ESTOP_OK_KEYS:
                # ok chain: green when ok, red when broken
                state = "good" if v else "bad"

            else:
                # other: amber only when asserted, otherwise off
                state = "warn" if v else None

            self._set_led_state_by_name(spec.dot, state)


    # ----- brake display helpers (match HiP) -----

    def _update_taster_edge_disp(self, taster: bool) -> None:
        """Track taster rising edge (0->1) for brake handoff grace."""
        prev = bool(getattr(self, "_taster_prev_disp", taster))
        if (not prev) and bool(taster):
            self._taster_pressed_s = time.monotonic()
        self._taster_prev_disp = bool(taster)

    def _within_brake_grace_disp(self) -> bool:
        """True if within grace window after taster rose."""
        t0 = getattr(self, "_taster_pressed_s", None)
        if t0 is None:
            return False
        return (time.monotonic() - float(t0)) <= float(getattr(self, "_BRAKE_HANDOFF_GRACE_S", 3.0))

    def _brake_ok_display_disp(self, *, brk_ok_raw: bool, taster: bool) -> bool:
        """
        Display 'brake state OK for current hold mode'.

        Legacy meaning behaves like equivalence (NOT XOR): brk_ok_raw == taster.
        Add SafetyPLC's grace after taster rises.
        """
        if bool(taster) and self._within_brake_grace_disp():
            return True
        return (bool(brk_ok_raw) == bool(taster))


    # ----- diagnostic actions -----

    def _set_inj_estop_all(self) -> None:
        # Set ALL logical bits to True
        for k in self._inj_bits.keys():
            self._inj_bits[k] = True
        self._inj_estop_word = encode_estop_word(self._inj_bits)
        log.info("inject: SET ALL bits (word=0x%08X)", self._inj_estop_word)
        self._render_estop_word_to_ui(self._inj_estop_word)

    def _clear_inj_estop_all(self) -> None:
        # Restore a stable "GO" state (healthy chain) instead of clearing everything.
        # This keeps ResetAble/OK bits true and avoids painting the operator into a corner.
        self._apply_go_state()
        log.info("inject: GO state (word=0x%08X)", self._inj_estop_word)


    def _emit_status(self, now_ns: int) -> None:
        """Emit a compact structured heartbeat for the supervisor birds-eye view."""
        if not getattr(self, "_status", None):
            return

        age_ms: float | None
        if self._last_cmd_ns is None:
            age_ms = None
        else:
            age_ms = (now_ns - self._last_cmd_ns) / 1_000_000.0

        stale = (age_ms is None) or (age_ms >= float(self.stale_after_ms))
        level = "ERR" if (self._last_estop or self._last_fault) else ("WARN" if stale else "OK")
        axis = self.axis_ids[0] if self.axis_ids else ""
        mode = self._last_mode or ""
        online = bool(self._seen_first_cmd) and (not stale)
        age_disp = "NA" if age_ms is None else f"{age_ms:.0f}"
        summary = f"axis={axis or '-'} mode={mode or '-'} online={int(online)} age_ms={age_disp}"

        try:
            self._status.emit_every(
                level=level,
                summary=summary,
                fields={
                    "axis": axis,
                    "mode": mode,
                    "online": bool(online),
                    "age_ms": (-1 if age_ms is None else float(age_ms)),
                    "stale": bool(stale),
                    "estop": bool(self._last_estop),
                    "fault": bool(self._last_fault),
                    "tick": int(getattr(self.state, "tick", 0) or 0),
                },
            )
        except Exception:
            pass


    # ----- runtime -----

    # --- Cut marker helpers -------------------------------------------------

    def _clear_cut_markers(self) -> None:
        """Clear latched cut markers and reset exported params."""
        self._cut_valid = False
        self._cut_pos_m = 0.0
        self._cut_vel_mps = 0.0
        self._cut_time_s = 0.0
        # Prevent immediate re-latch if we're still in estop
        self._prev_estop_state = bool(getattr(self.state, "estop", False))

        try:
            self.state.params["CutPos"] = 0.0
            self.state.params["CutVel"] = 0.0
            self.state.params["CutTime"] = 0.0
            self.state.params["PosDiffFor"] = 0.0
        except Exception:
            pass

    def _on_diag_resync_clicked(self) -> None:
        """Operator pressed ReSync: clear cut markers."""
        self._clear_cut_markers()
        # paint immediately
        self._render_cut_markers_to_ui(pos_m=None)

    def _render_cut_markers_to_ui(self, *, pos_m: float | None) -> None:
        """Render cut marker readouts. When no cut is latched, show '--'."""
        if not bool(getattr(self, "_cut_valid", False)):
            for w in (self._txt_cut_time, self._txt_cut_pos, self._txt_cut_vel, self._txt_posdiff):
                if w is not None:
                    w.setText("--")
            return

        if self._txt_cut_time is not None:
            self._txt_cut_time.setText(f"{float(self._cut_time_s):.2f} s")
        if self._txt_cut_pos is not None:
            self._txt_cut_pos.setText(f"{float(self._cut_pos_m):.2f} m")
        if self._txt_cut_vel is not None:
            self._txt_cut_vel.setText(f"{float(self._cut_vel_mps):.2f} m/s")

        if pos_m is None:
            if self._txt_posdiff is not None:
                self._txt_posdiff.setText("--")
            return

        pd = float(pos_m) - float(self._cut_pos_m)
        try:
            self.state.params["PosDiffFor"] = float(pd)
        except Exception:
            pass
        if self._txt_posdiff is not None:
            self._txt_posdiff.setText(f"{pd:.2f} m")



    def start(self) -> None:
        t = QTimer(self.win)
        t.setInterval(int(self.dt_s * 1000))
        t.timeout.connect(self.step_once)
        t.start()
        self._timer = t

    def step_once(self) -> None:
        frames = self._drain_command_frames_compat(limit=100)
        if frames:
            self._last_cmd = frames[-1]
            self._last_cmd_ns = time.monotonic_ns()
            self._seen_first_cmd = True
            self._hb.inc("cmd_rx", len(frames))
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

        # Header online dot: green when we are receiving command frames, amber when stale.
        self._render_header_online_dot()

        # Edge logs: command mode / reset changes
        try:
            if self._ch.changed("cmd_mode", str(getattr(self._last_cmd, "mode", ""))):
                log.info("cmd_mode=%s", getattr(self._last_cmd, "mode", ""))
            if self._ch.changed("cmd_estop_reset", bool(getattr(self._last_cmd, "estop_reset", False))):
                log.info("cmd_estop_reset=%s", bool(getattr(self._last_cmd, "estop_reset", False)))
        except Exception:
            pass

        # Reset => GO state (no flash)
        if bool(getattr(self._last_cmd, "estop_reset", False)):
            log.info("estop_reset received -> POST-RESET state (await Taster)")
            self._apply_post_reset_state()
            self._clear_cut_markers()
            self._render_cut_markers_to_ui(pos_m=None)

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

                # ST does *not* implement a param-edit session on the wire.
                # In simulation we still *support* edit sessions, but we also accept
                # direct writes when no session is active.

                # enforce minimal device-side guards too
                if str(grp) == 'pos':
                    vals = self._normalize_pos_chain(vals)
                elif str(grp) == 'guider':
                    vals = self._normalize_guider_range(vals)
                if self.state.param_edit_active and (str(grp) != self.state.param_edit_group):
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


        # SafetyPLC/drive handoff emulation (taster -> ready/brakes after delay)
        self._apply_startup_logic()

        estop_word = int(self._inj_estop_word)
        bits = decode_estop_word(estop_word)

        # trip only on actual "cause" bits (NOT on OK/status bits)
        trip = any(bool(bits.get(k, False)) for k in ESTOP_CAUSE_KEYS) or (not self._safety_ok)
        if trip:
            self._estop_latched = True

        self.state.estop = bool(self._estop_latched)
        self.state.estop_status_word = estop_word
        # --- Cut markers: latch on E-Stop ENTRY ---
        # We compute the edge here, but latch AFTER the plant step so we use the freshest measurement.
        estop_edge = bool(self.state.estop) and (not bool(self._prev_estop_state))

        # Clamp motion commands until the drive is actually ready (SafetyPLC handoff complete).
        cmd_for_plant = self._last_cmd
        if (not self._drive_ready) or self.state.estop:
            # disable all axes; keep the original cmd frame for UI display / logging
            cmd_for_plant = replace(
                self._last_cmd,
                axes={a: AxisSetpoint(enable=False, vel=0.0) for a in self.axis_ids},
            )

        self.device.step(self.state, cmd_for_plant, self.tb.dt_s)

        # Latch cut markers on the *edge* using the freshest post-step measurement (before estop clamping).
        if bool(estop_edge) and (not bool(self._cut_valid)):
            axis_id = self.axis_ids[0] if self.axis_ids else ""
            ax0 = self.state.axes.get(axis_id) if axis_id else None
            if ax0 is not None:
                self._cut_valid = True
                self._cut_pos_m = float(getattr(ax0, 'pos', 0.0) or 0.0)
                self._cut_vel_mps = float(getattr(ax0, 'vel', 0.0) or 0.0)
                self._cut_time_s = float(getattr(self.state, 't_s', 0.0) or 0.0)
                self.state.params['CutPos'] = float(self._cut_pos_m)
                self.state.params['CutVel'] = float(self._cut_vel_mps)
                self.state.params['CutTime'] = float(self._cut_time_s)
                self.state.params['PosDiffFor'] = 0.0


        if self.state.estop:
            for ax in self.state.axes.values():
                ax.enabled = False
                ax.vel = 0.0

        self.state.tick += 1
        self.state.t_s += self.tb.dt_s

        # Remember for next tick
        self._prev_estop_state = bool(self.state.estop)

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
                    # LifeTick is useful while debugging connectivity, but too chatty
                    # for everyday use. Keep it at DEBUG (edge-triggered).
                    log.debug(
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

            # Heartbeat focuses on the primary axis (first configured axis).
            if self.axis_ids and _axis_id == self.axis_ids[0]:
                self._hb.set("tx", int(tx))
                self._hb.set("rx", int(rx))
                self._hb.set("diff", int(diff))
                if self._last_cmd_ns is not None:
                    self._hb.set("cmd_age_ms", int((time.monotonic_ns() - self._last_cmd_ns) / 1_000_000.0))

            # LifeTick is noisy during normal operation. Keep a throttled trace at DEBUG.
            if self.axis_ids and _axis_id == self.axis_ids[0] and _lt_should_log(now_s, self._lt_last_telem_log_s):
                self._lt_last_telem_log_s = now_s
                log.debug(
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

        # Render live readouts in the DenSi UI (plausible defaults at startup)
        try:
            axis_id = self.axis_ids[0] if self.axis_ids else ""
            ax = self.state.axes.get(axis_id) if axis_id else None
            pos = float(getattr(ax, "pos", 0.0)) if ax else 0.0
            vel = float(getattr(ax, "vel", 0.0)) if ax else 0.0
            amp = float(self.state.params.get("ActCur", 0.0))
            tmp = float(self.state.params.get("Temp", 20.0))
            if self._txt_pos is not None:
                self._txt_pos.setText(f"{pos:.2f} m")
            if self._txt_vel is not None:
                self._txt_vel.setText(f"{vel:.2f} m/s")
            if self._txt_amp is not None:
                self._txt_amp.setText(f"{int(round(amp))} A")
            if self._txt_temp is not None:
                self._txt_temp.setText(f"{int(round(tmp))}°")


            # Cut marker readouts
            self._render_cut_markers_to_ui(pos_m=pos)


            # Guider readouts (defaults if not yet modeled)
            g_min = float(self.state.params.get("PosMin", 0.0) or 0.0)
            g_max = float(self.state.params.get("PosMax", 0.0) or 0.0)
            g_val = float(self.state.params.get("GuidePosIst", 0.0) or 0.0)
            g_spd = float(self.state.params.get("GuideIstSpeed", 0.0) or 0.0)
            if self._txt_guider_range_min is not None:
                self._txt_guider_range_min.setText(f"{g_min:.3f} m")
            if self._txt_guider_range_max is not None:
                self._txt_guider_range_max.setText(f"{g_max:.3f} m")
            if self._txt_guider_range_val is not None:
                self._txt_guider_range_val.setText(f"{g_val:.3f} m")
            if self._txt_guider_speed is not None:
                self._txt_guider_speed.setText(f"{g_spd:.3f} m/s")

            # --- slider indicators ---
            # sldVelCmd: show commanded velocity (setpoint) with range ±VelMax
            vel_max = float(self.state.params.get("VelMax", 0.0) or 0.0)
            if vel_max <= 0.0:
                vel_max = 1.0
            vel_cmd = 0.0
            try:
                if self._last_cmd is not None and axis_id and hasattr(self._last_cmd, "axes"):
                    sp = self._last_cmd.axes.get(axis_id)
                    if sp is not None:
                        vel_cmd = float(getattr(sp, "vel", 0.0))
            except Exception:
                vel_cmd = 0.0
            if self._sld_vel_cmd is not None:
                scale = 1000.0  # m/s -> mm/s for slider resolution
                self._sld_vel_cmd.blockSignals(True)
                self._sld_vel_cmd.setMinimum(int(round(-vel_max * scale)))
                self._sld_vel_cmd.setMaximum(int(round(+vel_max * scale)))
                self._sld_vel_cmd.setValue(int(round(vel_cmd * scale)))
                self._sld_vel_cmd.blockSignals(False)

            # sldLimitRange: show current position in [UserMin, UserMax]
            user_min = float(self.state.params.get("UserMin", 0.0) or 0.0)
            user_max = float(self.state.params.get("UserMax", 0.0) or 0.0)
            if user_max < user_min:
                user_min, user_max = user_max, user_min
            if self._sld_limit_range is not None:
                scale = 1000.0  # m -> mm for slider resolution
                self._sld_limit_range.blockSignals(True)
                self._sld_limit_range.setMinimum(int(round(user_min * scale)))
                self._sld_limit_range.setMaximum(int(round(user_max * scale)))
                self._sld_limit_range.setValue(int(round(pos * scale)))
                self._sld_limit_range.blockSignals(False)

        except Exception:
            pass

        # Provide plausible legacy drive status words so HiP's AmpStatus fields light up.
        self._update_drive_status_words()

        snap = TelemetrySnapshot.from_state(self.state)
        self._publish_telemetry_compat(snap)

        # Edge logs for key state changes.
        if self._ch.changed("mode", str(getattr(snap, "mode", ""))):
            log.info("mode=%s", getattr(snap, "mode", ""))
        if self._ch.changed("estop", bool(getattr(snap, "estop", False))):
            log.info("estop=%s word=%s", bool(getattr(snap, "estop", False)), hex(int(getattr(snap, "estop_status_word", 0))))
        if self._ch.changed("fault", bool(getattr(snap, "fault", False))):
            log.info("fault=%s", bool(getattr(snap, "fault", False)))

        # Heartbeat summary (1 Hz)
        self._hb.inc("telem_tx", 1)
        self._hb.set("tick", int(getattr(snap, "tick", 0)))
        self._hb.set("mode", str(getattr(snap, "mode", "")))
        self._hb.set("estop", bool(getattr(snap, "estop", False)))
        self._hb.set("fault", bool(getattr(snap, "fault", False)))
        if self.axis_ids:
            self._hb.set("axis", self.axis_ids[0])
        if self._last_cmd_ns is not None:
            self._hb.set("cmd_age_ms", int((time.monotonic_ns() - self._last_cmd_ns) / 1_000_000.0))
        self._hb.emit(log)
        self._last_mode = str(getattr(self._last_cmd, "mode", "") or "")
        self._last_estop = bool(getattr(self._last_cmd, "estop", False))
        self._last_fault = bool(getattr(self._last_cmd, "fault", False))
        self._emit_status(time.monotonic_ns())

        log.debug("device_tick=%s", self.state.axes[next(iter(self.state.axes))].meta.get("device_tick"))

        log.debug(
            "tx telem: tick=%s estop=%s fault=%s estop_word=%s",
            snap.tick, snap.estop, snap.fault, hex(snap.estop_status_word),
        )
