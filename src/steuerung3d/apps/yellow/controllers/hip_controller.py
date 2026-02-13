# src/steuerung3d/apps/yellow/controllers/hip_controller.py
from __future__ import annotations

from dataclasses import dataclass
import logging
import time
import math
import uuid

from PySide6.QtCore import QLocale, QTimer
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QAbstractSlider,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QWidget,
)

from steuerung3d.core.intents import (
    ClaimAxis,
    EchoLifeTick,
    ParamCancel,
    ParamEditBegin,
    ParamWrite,
    ReleaseAxis,
    RequestEstopReset,
    RequestResync,
)
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.estop_bits import (
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    ESTOP_SPECS,
    decode_estop_word,
)
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat
from steuerung3d.util.tick import compute_time_tick

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter  # type: ignore
except Exception:  # pragma: no cover
    StatusEmitter = None  # type: ignore

from .bindings import YellowBindings
from .ports import IntentOut, TelemetryIn

# NOTE: You MUST have this decoder somewhere in your codebase.
# If the import path differs, adjust it here.
# The object returned must have:
#   - .summary() -> str
#   - .output_powered -> bool
try:
    from steuerung3d.protocol.drive_status import decode_drive_status  # type: ignore
except Exception:  # pragma: no cover
    decode_drive_status = None  # type: ignore

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
        "PosMin": "txtGPosMin_3",
        "PosMax": "txtGPosMax_2",
        "Pitch": "txtPitch_2",
    },
}

# Axis selection sentinel for pooled HiP panels
NOT_ATTACHED = "NotAttached"

# Compact limit display fields in the header bar (meters)
_LIMIT_WIDGETS: dict[str, str] = {
    "HardMin": "txtLimitHardMin",
    "UserMin": "txtLimitUserMin",
    "UserMax": "txtLimitUserMax",
    "HardMax": "txtLimitHardMax",
}
# --- Header banner: EsState (from EStopStatus word only) -----------------------
_BANNER_COLORS: dict[str, tuple[str, str]] = {
    "ESTOP": ("#F9E547", "#000000"),  # yellow
    "IDLE": ("#FFB300", "#000000"),   # amber
    "ARMED": ("#1B5E20", "#FFFFFF"),  # dark green
    "READY": ("#2E7D32", "#FFFFFF"),  # green
}

_BANNER_DYNAMIC_EXCLUDE: set[str] = {
    # exclude dynamic bits from OK-chain trip evaluation (except brakes, handled separately)
    "ready",
    "taster",
    "schuetz",
    "reset_able",
    "steuerwort",
    "key1_ok",
    "key2_ok",
}


def _parse_estop_word_from_snapshot(snap: TelemetrySnapshot) -> int:
    # Prefer raw field if present (string), fallback to typed field.
    fields = getattr(snap, "plc_uplink_fields", None)
    if isinstance(fields, dict):
        v = fields.get("EStopStatus")
        if v is not None:
            try:
                return int(str(v).strip())
            except Exception:
                pass
    return int(getattr(snap, "estop_status_word", 0) or 0)


@dataclass
class HiPController:
    win: QWidget
    intent_out: IntentOut
    telemetry_in: TelemetryIn

    # If we stop receiving telemetry for this long, we go back to UNKNOWN
    stale_after_ms: int = 500

    # hard-baked in SafetyPLC
    _BRAKE_HANDOFF_GRACE_S: float = 3.0

    # ---------- deadman/brake display helpers ----------

    def _update_taster_edge(self, axis_id: str, taster: bool) -> None:
        """Track taster rising edge (0->1) so we can apply the 3s brake handoff grace."""
        prev = self._taster_prev.get(axis_id, taster)
        if (not prev) and taster:
            self._taster_pressed_s[axis_id] = time.monotonic()
        self._taster_prev[axis_id] = taster

    def _within_brake_grace(self, axis_id: str) -> bool:
        """True if within 3 seconds after taster rose."""
        t0 = self._taster_pressed_s.get(axis_id)
        if t0 is None:
            return False
        return (time.monotonic() - t0) <= float(self._BRAKE_HANDOFF_GRACE_S)


    def _within_banner_brake_grace(self, axis_id: str) -> bool:
        """True if within 2 seconds after taster rose (for banner trip/estate decode)."""
        t0 = self._taster_pressed_s.get(axis_id)
        if t0 is None:
            return False
        return (time.monotonic() - t0) <= 2.0

    def _banner_estate_from_word(self, *, axis_id: str, word: int) -> str:
        # Default is ESTOP (startup, or unknown)
        w = int(word) & 0xFFFFFFFF
        if w == 0:
            return "ESTOP"

        bits = decode_estop_word(w)

        # Trip cause bits always force ESTOP
        trip_cause = any(bool(bits.get(k, False)) for k in ESTOP_CAUSE_KEYS)

        # OK-chain trip evaluation: exclude dynamic bits, handle brake bits separately
        ok_keys = [k for k in ESTOP_OK_KEYS if (k not in _BANNER_DYNAMIC_EXCLUDE) and (k not in ("brk1_ok", "brk2_ok"))]
        ok_chain_fault = any(not bool(bits.get(k, True)) for k in ok_keys)

        taster = bool(bits.get("taster", False))
        schuetz = bool(bits.get("schuetz", False))
        brk_ok = bool(bits.get("brk1_ok", True)) and bool(bits.get("brk2_ok", True))

        # Brake bits: only become a trip after grace when taster is ON.
        # When taster is OFF, brake OK must be true (brakes applied and watchers OK) => trip if false.
        if taster:
            brake_trip = (not brk_ok) and (not self._within_banner_brake_grace(axis_id))
        else:
            brake_trip = (not brk_ok)

        trip_active = trip_cause or ok_chain_fault or brake_trip
        if trip_active:
            return "ESTOP"

        # Ladder: Schuetz -> IDLE, Taster -> ARMED, Brakes lifted -> READY
        if not schuetz:
            return "ESTOP"
        if not taster:
            return "IDLE"
        return "READY" if brk_ok else "ARMED"

    def _apply_banner_estate(self, estate: str) -> None:
        bg, fg = _BANNER_COLORS.get(estate, ("#F9E547", "#000000"))
        for w in (self._txt_hdr_banner_left, self._txt_hdr_banner_right):
            if w is None:
                continue
            w.setText(estate)
            w.setStyleSheet(f"background-color: {bg}; color: {fg}; font-weight: 700;")

    def _brake_ok_display(self, *, brk_ok_raw: bool, taster: bool, axis_id: str) -> bool:
        """
        Display 'brake state OK for current hold mode'.

        Legacy meaning behaves like equivalence (NOT XOR): brk_ok_raw == taster.
        Add SafetyPLC's 3s handoff grace after taster rises.
        """
        if taster and self._within_brake_grace(axis_id):
            return True
        return bool(brk_ok_raw)

    # ---------- init ----------

    def __post_init__(self) -> None:
        self.ui = YellowBindings.from_window(self.win)

        # Estop diagnostics checkboxes (present in the HiP UI but *read-only*).
        self._estop_checks: dict[str, QCheckBox] = {}
        for spec in ESTOP_SPECS.values():
            if not spec.checkbox:
                continue
            w = self.win.findChild(QCheckBox, spec.checkbox)
            if w is not None:
                w.setEnabled(False)
                self._estop_checks[spec.key] = w

        # Logging helpers: 1 Hz heartbeat + edge logs.
        self._hb = Heartbeat("hi_p", interval_s=1.0)
        self._ch = ChangeTracker()

        # Structured status heartbeat (side-channel for supervisor birds-eye; PLC packets unchanged)
        self._status = StatusEmitter.from_env(default_service="hi_p") if StatusEmitter else None
        self._last_mode: str = ""
        self._last_estop: bool = False
        self._last_fault: bool = False

        self._seen_first_telem = False
        self._last_rx_ns: int | None = None
        self._timer: QTimer | None = None

        # HiP identity and current axis selection
        self._hip_id: str = f"hip-{uuid.uuid4().hex[:8]}"
        self._cmb_axis: QComboBox | None = self.win.findChild(QComboBox, "cmb_axis")

        # Legacy TimeTick display (ticks elapsed between telemetry updates)
        self._txt_tick: QLineEdit | None = self.win.findChild(QLineEdit, "txt_tick")

        # Live readouts (same widgets exist in the HiP UI)
        self._txt_pos: QLineEdit | None = self.win.findChild(QLineEdit, "txt_pos")
        self._txt_vel: QLineEdit | None = self.win.findChild(QLineEdit, "txt_vel")
        self._txt_amp: QLineEdit | None = self.win.findChild(QLineEdit, "txt_amp")
        self._txt_temp: QLineEdit | None = self.win.findChild(QLineEdit, "txt_temp")

        # Cut markers (read-only fields)
        self._txt_cut_pos: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_pos")
        self._txt_cut_vel: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_vel")
        self._txt_cut_time: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_time")
        self._txt_posdiff: QLineEdit | None = self.win.findChild(QLineEdit, "txt_posdiff")

        # HiP should not show DenSi-only SafetyPLC Start button
        _esstart = self.win.findChild(QPushButton, "btnESStart")
        if _esstart is not None:
            _esstart.hide()
            _esstart.setEnabled(False)

        self._btn_diag_resync: QPushButton | None = (self.win.findChild(QPushButton, "btnReSync")
            or self.win.findChild(QPushButton, "btnDiagResync"))
        if self._btn_diag_resync is not None:
            self._btn_diag_resync.clicked.connect(self._on_diag_resync_clicked)


        # Sliders used as live indicators
        self._sld_vel_cmd: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldVelCmd")
        self._sld_limit_range: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldLimitRange")
        self._sld_guider_range: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldGuiderRange")
        self._sld_guider_speed: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldGuiderSpeed")

        # Guider readouts (DenSi-compatible names)
        self._txt_guider_range_min: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeMin")
        self._txt_guider_range_max: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeMax")
        self._txt_guider_range_val: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeValue")
        # renamed from txtGuiderPos_2 -> txtGuiderSpeed
        self._txt_guider_speed: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderSpeed")
        if self._txt_guider_speed is None:
            self._txt_guider_speed = self.win.findChild(QLineEdit, "txtGuiderPos_2")

        # Legacy drive status fields (main + guider/slave)
        self._txt_main_amp_status: QLineEdit | None = self.win.findChild(QLineEdit, "txtMainAmpStatus")
        self._txt_slave_amp_status: QLineEdit | None = self.win.findChild(QLineEdit, "txtSlaveAmpStatus")
        self._txt_hdr_banner_left: QLineEdit | None = self.win.findChild(QLineEdit, "txtHdrBannerLeft")
        self._txt_hdr_banner_right: QLineEdit | None = self.win.findChild(QLineEdit, "txtHdrBannerRight")

        self._prev_device_tick: int | None = None

        # Last EchoLifeTick sent per axis (avoid spamming duplicates)
        self._last_lifetick_echo_sent: dict[str, int] = {}

        self._selected_axis: str = ""
        self._fixed_axis: str = ""
        self._lock_axis_combo: bool = False
        self._fixed_axis_applied: bool = False
        if self._cmb_axis is not None:
            self._cmb_axis.currentTextChanged.connect(self._on_axis_selected)
        # --- controller state used by UI gating (must exist before _set_attach_ui_state) ---
        # Pending transactions keyed by req_id -> info (used by _is_group_busy / param UI state)
        self._pending_txn: dict[str, object] = {}
        # Local edit state (mirrors telemetry but must be safe at startup)
        self._local_edit_active: bool = False
        self._local_edit_group: str = ""

        # Modal param edit lock bookkeeping (used by _set_modal_param_lock)
        self._modal_locked: bool = False
        self._modal_prev_enabled: dict[QWidget, bool] = {}
        self._modal_prev_tabbar_enabled: bool | None = None

        # Start in 'unattached' visual state for pooled HiP panels.
        self._set_attach_ui_state(attached=bool(self._fixed_axis))


        # After write/cancel, ignore remote edit flags briefly to avoid UI flicker
        self._ignore_remote_edit_until_ns: int = 0

        # Param commit observation dialog (Option A: show only after applied/timeout)
        self._pending_commit_req_id: str = ""
        self._pending_commit_group: str = ""
        self._pending_commit_values: dict[str, float] = {}
        self._commit_dialog_shown_for: set[str] = set()

        # Deadman (taster) edge tracking for brake handoff display grace.
        self._taster_prev: dict[str, bool] = {}
        self._taster_pressed_s: dict[str, float] = {}

        # HIP<->Core transactional param intents (best-effort reliability)
        self._req_seq: int = 0
        self._session_by_group: dict[str, str] = {}
        self._pending_txn: dict[str, dict] = {}
        self._resend_after_ms: int = 250
        self._max_retries: int = 8

        # Local UI-driven edit state
        self._local_edit_group: str = ""
        self._local_edit_active: bool = False

        if self.ui.btn_estop_reset is not None:
            self.ui.btn_estop_reset.clicked.connect(self._on_estop_reset)
            log.info("wired: btnEStopReset -> RequestEstopReset intent")
            self.ui.btn_estop_reset.setEnabled(False)
        else:
            log.warning("btnEStopReset not found in UI")

        # parameter buttons (axis-agnostic v0.1)
        self._wire_param_buttons()

        # validators
        self._init_param_inputs()

        # Parameter UI starts locked
        self._apply_param_ui_state(edit_active=False, edit_group="")

        # paint all known dots as "unknown"
        self._set_all_estop_unknown()
        if self._txt_tick is not None:
            self._txt_tick.setText("--")
        self._prev_device_tick = None

    # ---------- public helpers ----------

    def set_fixed_axis(self, axis_id: str, *, lock_combo: bool = True) -> None:
        self._fixed_axis = (axis_id or "").strip()
        self._lock_axis_combo = bool(lock_combo)
        self._fixed_axis_applied = False
        if self._fixed_axis:
            try:
                self.win.setWindowTitle(f"HMI – HiP ({self._fixed_axis})")
            except Exception:
                pass

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

    def _attached_axis(self) -> str:
        return (self._selected_axis or self._fixed_axis or "").strip()

    def _require_attached(self) -> str | None:
        axis = self._attached_axis()
        if not axis:
            return None
        return axis

    def _clear_text_fields_for_unattached(self) -> None:
        # Clear all line edits except tick.
        for le in self.win.findChildren(QLineEdit):
            try:
                if le is self._txt_tick:
                    continue
                le.setText("")
            except Exception:
                pass
        if self._txt_tick is not None:
            self._txt_tick.setText("--")
        self._prev_device_tick = None

        # Clear a few known header/status fields if present
        for w in (self._txt_main_amp_status, self._txt_slave_amp_status, self._txt_hdr_banner_left, self._txt_hdr_banner_right):
            if w is not None:
                try:
                    w.setText("")
                except Exception:
                    pass

    def _set_attach_ui_state(self, *, attached: bool) -> None:
        """Unattached = dead panel (grey + empty). Attached = normal (telemetry drives values).

        Everything is disabled when unattached, except cmb_axis so the user can attach.
        """
        tabs = self.win.findChild(QTabWidget, "tabsMain")

        if tabs is not None:
            if not attached:
                tabs.setEnabled(False)
            else:
                # Modal lock overrides; don't re-enable while locked.
                if not self._modal_locked:
                    tabs.setEnabled(True)

        # Keep axis combo usable in pool mode, unless locked to fixed axis.
        if self._cmb_axis is not None:
            try:
                if self._lock_axis_combo and self._fixed_axis_applied:
                    self._cmb_axis.setEnabled(False)
                else:
                    self._cmb_axis.setEnabled(True)
            except Exception:
                pass

        # Setup toggle should be greyed out when unattached.
        btn_setup = self._find_button("btnSetupToggle")
        btn_Mainampreset = self._find_button("btn_reset")
        if btn_Mainampreset is not None:
            try:
                btn_Mainampreset.setEnabled(bool(attached) and (not self._modal_locked))
            except Exception:
                pass
        if btn_setup is not None:
            try:
                btn_setup.setEnabled(bool(attached) and (not self._modal_locked))
            except Exception:
                pass

        # Recover disabled always for now.
        btn_rec = self._find_button("btnRecover")
        if btn_rec is not None:
            try:
                btn_rec.setEnabled(False)
            except Exception:
                pass

        # E-stop reset disabled when unattached (telemetry enables it when attached)
        if self.ui.btn_estop_reset is not None and not attached:
            self.ui.btn_estop_reset.setEnabled(False)

        if not attached:
            self._clear_text_fields_for_unattached()

            # Neutralize header dots
            for n in ("dotHdrOnline", "dotHdrReady", "dotHdrFbt", "dotHdrBrake1", "dotHdrBrake2"):
                self._set_led_by_name(n, state=None)

            # Neutralize estop dots and checkboxes (no stale state)
            for spec in ESTOP_SPECS.values():
                if spec.dot:
                    self._set_led_by_name(spec.dot, state=None)
            for cb in getattr(self, "_estop_checks", {}).values():
                try:
                    cb.setChecked(False)
                except Exception:
                    pass

            # Ensure param edit UI is not in edit mode
            self._local_edit_active = False
            self._local_edit_group = ""
            self._apply_param_ui_state(edit_active=False, edit_group="")

        else:
            # Restore param button availability to whatever our local state is
            self._apply_param_ui_state(edit_active=self._local_edit_active, edit_group=self._local_edit_group)

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
        if self._txt_tick is not None:
            self._txt_tick.setText("--")
        self._prev_device_tick = None

    # ---------- intents ----------

    def _on_estop_reset(self) -> None:
        axis = self._require_attached()
        if axis is None:
            return
        intent = RequestEstopReset(axis_id=axis, hip_id=self._hip_id)
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
        loc = QLocale.system()
        for _grp, mapping in _PARAM_WIDGETS.items():
            for _key, obj_name in mapping.items():
                le = self._find_line_edit(obj_name)
                if le is None:
                    continue
                le.setProperty("paramField", "true")
                val = QDoubleValidator(-1.0e12, 1.0e12, 6, le)
                val.setLocale(loc)
                val.setNotation(QDoubleValidator.Notation.StandardNotation)
                le.setValidator(val)
                le.style().unpolish(le)
                le.style().polish(le)
                le.update()

    def _parse_float(self, s: str) -> float:
        s = (s or "").strip()
        if not s:
            return 0.0
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

        if group == "pos":
            self._render_limit_fields(values)

    def _fmt_m(self, v: float) -> str:
        try:
            s = f"{float(v):0.2f} m"
        except Exception:
            s = ""
        return s.replace(".", ",")

    def _render_limit_fields(self, values: dict[str, float]) -> None:
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
            try:
                le.setEnabled(False)
            except Exception:
                pass

    def _normalize_pos_chain(self, values: dict[str, float]) -> dict[str, float]:
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

        user_max = max(min(user_max, hard_max), hard_min)
        user_min = max(min(user_min, user_max), hard_min)

        v["HardMax"] = hard_max
        v["HardMin"] = hard_min
        v["UserMax"] = user_max
        v["UserMin"] = user_min
        return v

    def _normalize_guider_range(self, values: dict[str, float]) -> dict[str, float]:
        v = dict(values)
        if "PosMin" not in v or "PosMax" not in v:
            return v
        pos_min = float(v["PosMin"])
        pos_max = float(v["PosMax"])
        if pos_min > pos_max:
            pos_min = pos_max
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
            if bw is not None:
                bw.clicked.connect(lambda _=False, g=grp: self._tx_param_write(g))
            if bc is not None:
                bc.clicked.connect(lambda _=False, g=grp: self._tx_param_cancel(g))

    def _tx_param_edit(self, group: str) -> None:
        axis = self._require_attached()
        if axis is None:
            return
        self._local_edit_active = True
        self._local_edit_group = group
        self._apply_param_ui_state(edit_active=True, edit_group=group)

        session_id = f"sess-{group}-{int(time.monotonic()*1000)}"
        self._session_by_group[group] = session_id
        req_id = self._next_req_id()

        intent = ParamEditBegin(
            axis_id=axis,
            hip_id=self._hip_id,
            group=group,
            req_id=req_id,
            session_id=session_id,
        )
        log.info("tx intent: %s group=%s req_id=%s session=%s", type(intent).__name__, group, req_id, session_id)
        self._send_txn_intent(intent, group=group, kind="begin")

    def _tx_param_write(self, group: str) -> None:
        axis = self._require_attached()
        if axis is None:
            return
        vals = self._read_param_values(group)

        fixed = dict(vals)
        if group == "pos":
            fixed = self._normalize_pos_chain(fixed)
        elif group == "guider":
            fixed = self._normalize_guider_range(fixed)

        if fixed != vals:
            log.info("param guards adjusted %s values (writing back to UI)", group)
            self._write_back_values(group, fixed)

            if group == "pos":
                def _fmt(x: float) -> str:
                    return f"{float(x):g}"

                lines = []
                for k in ("HardMax", "UserMax", "UserMin", "HardMin"):
                    if k in vals and k in fixed and float(vals[k]) != float(fixed[k]):
                        lines.append(f"{k}: {_fmt(vals[k])} → {_fmt(fixed[k])}")
                if lines:
                    QMessageBox.information(
                        self.win,
                        "Position limits adjusted",
                        "The rule HardMax ≥ UserMax ≥ UserMin ≥ HardMin was enforced.\n\n" + "\n".join(lines),
                    )

        session_id = self._ensure_session(group)
        req_id = self._next_req_id()
        intent = ParamWrite(
            axis_id=axis,
            hip_id=self._hip_id,
            group=group,
            values=fixed,
            req_id=req_id,
            session_id=session_id,
        )
        self._send_txn_intent(intent, group=group, kind="write")

        self._pending_commit_req_id = req_id
        self._pending_commit_group = group
        self._pending_commit_values = dict(fixed)

        self._local_edit_active = False
        self._local_edit_group = ""
        self._ignore_remote_edit_until_ns = time.monotonic_ns() + 800_000_000
        self._apply_param_ui_state(edit_active=False, edit_group="")

    def _tx_param_cancel(self, group: str) -> None:
        axis = self._require_attached()
        if axis is None:
            return
        session_id = self._ensure_session(group)
        req_id = self._next_req_id()
        intent = ParamCancel(
            axis_id=axis,
            hip_id=self._hip_id,
            group=group,
            req_id=req_id,
            session_id=session_id,
        )
        self._send_txn_intent(intent, group=group, kind="cancel")

        self._local_edit_active = False
        self._local_edit_group = ""
        self._ignore_remote_edit_until_ns = time.monotonic_ns() + 800_000_000
        self._apply_param_ui_state(edit_active=False, edit_group="")

    # ---------- HIP<->Core transactional helpers ----------

    def _next_req_id(self) -> str:
        self._req_seq += 1
        return f"hip-{self._req_seq:06d}"

    def _ensure_session(self, group: str) -> str:
        sid = self._session_by_group.get(group)
        if not sid:
            sid = f"sess-{group}-{int(time.monotonic()*1000)}"
            self._session_by_group[group] = sid
        return sid

    def _send_txn_intent(self, intent, *, group: str, kind: str = "") -> None:
        req_id = getattr(intent, "req_id", "")
        if req_id:
            self._pending_txn[req_id] = {
                "intent": intent,
                "group": group,
                "kind": kind,
                "sent_ns": time.monotonic_ns(),
                "retries": 0,
            }
        self.intent_out.publish_intent(intent)

    def _handle_core_acks(self, snap: TelemetrySnapshot) -> None:
        acks = getattr(snap, "core_acks", []) or []
        for rid in list(acks):
            if rid in self._pending_txn:
                self._pending_txn.pop(rid, None)
                log.info("core ack: %s", rid)

        self._apply_param_ui_state(edit_active=self._local_edit_active, edit_group=self._local_edit_group)

    def _retry_pending(self, now_ns: int) -> None:
        if not self._pending_txn:
            return
        resend_after_ns = int(self._resend_after_ms) * 1_000_000
        for rid, info in list(self._pending_txn.items()):
            sent_ns = int(info.get("sent_ns", 0))
            retries = int(info.get("retries", 0))
            if now_ns - sent_ns < resend_after_ns:
                continue
            if retries >= self._max_retries:
                log.error("txn give up: %s after %s retries (%s)", rid, retries, type(info.get("intent")).__name__)
                self._pending_txn.pop(rid, None)
                continue
            intent = info.get("intent")
            info["retries"] = retries + 1
            info["sent_ns"] = now_ns
            log.warning("txn resend: %s retry=%s %s", rid, info["retries"], type(intent).__name__ if intent else "<?>")
            if intent is not None:
                self.intent_out.publish_intent(intent)

    def _is_group_busy(self, group: str) -> bool:
        for info in getattr(self, '_pending_txn', {}).values():
            if info.get("group") != group:
                continue
            if str(info.get("kind") or "") in ("write", "cancel"):
                return True
        return False

    # ----- modal lock helpers -----

    def _set_modal_param_lock(self, *, active: bool, group: str) -> None:
        tabs = self.win.findChild(QTabWidget, "tabsMain")

        if active and not self._modal_locked:
            self._modal_prev_enabled = {}

            if tabs is not None:
                self._modal_prev_tabbar_enabled = bool(tabs.tabBar().isEnabled())
                tabs.tabBar().setEnabled(False)

            for w in self.win.findChildren(QWidget):
                if isinstance(w, (QPushButton, QLineEdit)):
                    self._modal_prev_enabled[w] = bool(w.isEnabled())
                    w.setEnabled(False)

            allow: list[QWidget] = []
            for _k, obj_name in _PARAM_WIDGETS.get(group, {}).items():
                le = self._find_line_edit(obj_name)
                if le is not None:
                    allow.append(le)

            wiring = {
                "pos": ("btnPosWrite", "btnPosCancel"),
                "vel": ("btnVelWrite", "btnVelCancel"),
                "filter": ("btnFilterWrite", "btnFilterCancel"),
                "guider": ("btnGuiderWrite", "btnGuiderCancel"),
            }
            if group in wiring:
                bw = self._find_button(wiring[group][0])
                bc = self._find_button(wiring[group][1])
                if bw is not None:
                    allow.append(bw)
                if bc is not None:
                    allow.append(bc)

            for w in allow:
                w.setEnabled(True)
                if isinstance(w, QLineEdit):
                    w.style().unpolish(w)
                    w.style().polish(w)
                    w.update()

            self._modal_locked = True
            return

        if (not active) and self._modal_locked:
            for w, was_enabled in list(self._modal_prev_enabled.items()):
                try:
                    w.setEnabled(bool(was_enabled))
                    if isinstance(w, QLineEdit):
                        w.style().unpolish(w)
                        w.style().polish(w)
                        w.update()
                except RuntimeError:
                    pass
            self._modal_prev_enabled.clear()

            if tabs is not None and self._modal_prev_tabbar_enabled is not None:
                tabs.tabBar().setEnabled(bool(self._modal_prev_tabbar_enabled))
            self._modal_prev_tabbar_enabled = None
            self._modal_locked = False

    # ----- parameters: UI state reflection (axis-agnostic v0.1) -----

    def _set_param_group_enabled(self, group: str, enabled: bool) -> None:
        mapping = _PARAM_WIDGETS.get(group, {})
        for _key, obj_name in mapping.items():
            le = self._find_line_edit(obj_name)
            if le is None:
                continue
            le.setEnabled(bool(enabled))
            le.style().unpolish(le)
            le.style().polish(le)
            le.update()

    def _set_param_button_state(self, group: str, *, editing: bool, busy: bool) -> None:
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

        if busy:
            if be is not None:
                be.setEnabled(False)
            if bw is not None:
                bw.setEnabled(False)
            if bc is not None:
                bc.setEnabled(False)
            return

        if be is not None:
            be.setEnabled(not editing)
        if bw is not None:
            bw.setEnabled(editing)
        if bc is not None:
            bc.setEnabled(editing)

    def _apply_param_ui_state(self, *, edit_active: bool, edit_group: str) -> None:
        groups = ("pos", "vel", "filter", "guider")

        self._set_modal_param_lock(active=bool(edit_active), group=str(edit_group or ""))

        if edit_active:
            for g in groups:
                if g == edit_group:
                    busy = self._is_group_busy(g)
                    self._set_param_group_enabled(g, bool(not busy))
                    self._set_param_button_state(g, editing=True, busy=busy)
                else:
                    self._set_param_group_enabled(g, False)
                    self._set_param_button_state(g, editing=False, busy=True)
            return

        for g in groups:
            busy = self._is_group_busy(g)
            self._set_param_group_enabled(g, False)
            self._set_param_button_state(g, editing=False, busy=busy)

    def _render_params_from_telemetry(self, snap: TelemetrySnapshot) -> None:
        params = getattr(snap, "params", None)
        if not isinstance(params, dict) or not params:
            return

        freeze_group = self._local_edit_group if self._local_edit_active else ""

        for grp, mapping in _PARAM_WIDGETS.items():
            if freeze_group and grp == freeze_group:
                continue
            for key, obj_name in mapping.items():
                if key not in params:
                    continue
                le = self._find_line_edit(obj_name)
                if le is None or le.hasFocus():
                    continue
                val = params[key]
                txt = f"{val:g}" if isinstance(val, (int, float)) else str(val)
                if le.text() == txt:
                    continue
                was = le.blockSignals(True)
                le.setText(txt)
                le.blockSignals(was)

        try:
            self._render_limit_fields({k: float(params[k]) for k in ("HardMin", "UserMin", "UserMax", "HardMax") if k in params})
        except Exception:
            pass

    def _render_params_and_edit_state(self, snap: TelemetrySnapshot) -> None:
        self._render_params_from_telemetry(snap)
        self._maybe_show_param_commit_dialog(snap)

        if self._local_edit_active:
            self._apply_param_ui_state(edit_active=True, edit_group=self._local_edit_group)
            return

        now_ns = time.monotonic_ns()
        if now_ns < int(self._ignore_remote_edit_until_ns or 0):
            edit_active = False
            edit_group = ""
        else:
            edit_active = bool(getattr(snap, "param_edit_active", False))
            edit_group = str(getattr(snap, "param_edit_group", "") or "")
        self._apply_param_ui_state(edit_active=edit_active, edit_group=edit_group)

    def _maybe_show_param_commit_dialog(self, snap: TelemetrySnapshot) -> None:
        rid = str(getattr(snap, "param_commit_req_id", "") or "")
        status = str(getattr(snap, "param_commit_status", "idle") or "idle")
        group = str(getattr(snap, "param_commit_group", "") or "")
        if not rid or rid != self._pending_commit_req_id:
            return
        if rid in self._commit_dialog_shown_for:
            return
        if status not in ("applied", "timeout"):
            return

        self._commit_dialog_shown_for.add(rid)

        if status == "applied":
            QMessageBox.information(self.win, "Parameters applied", f"{group} parameters were applied (observed in telemetry).")
        else:
            unmatched = list(getattr(snap, "param_commit_unmatched", []) or [])
            params = dict(getattr(snap, "params", {}) or {})
            want = dict(self._pending_commit_values or {})

            lines = [f"{group} parameters were not confirmed (timeout).", "", "Mismatches:"]
            for k in unmatched:
                w = want.get(k, "?")
                g = params.get(k, "<missing>")
                lines.append(f"- {k}: want {w}  got {g}")
            QMessageBox.warning(self.win, "Parameters not confirmed", "\n".join(lines))

        self._pending_commit_req_id = ""
        self._pending_commit_group = ""
        self._pending_commit_values = {}


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
        axis = self._selected_axis or self._fixed_axis or ""
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
            pass


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

        self._retry_pending(now_ns)

        if not snaps:
            if self._last_rx_ns is not None:
                age_ms = (now_ns - self._last_rx_ns) / 1_000_000.0
                if age_ms >= float(self.stale_after_ms):
                    self._last_rx_ns = None
                    self._mark_disconnected()
            self._emit_status(now_ns)
            return

        for _s in snaps:
            self._handle_core_acks(_s)

        snap = snaps[-1]
        self._last_rx_ns = now_ns

        try:
            self._update_axis_combo(snap)
            # In pooled mode we ignore telemetry rendering until user attaches to a device.
            if not self._attached_axis():
                self._emit_status(now_ns)
                return


            if not self._seen_first_telem:
                log.info("rx first telemetry: tick=%s estop=%s fault=%s", getattr(snap, "tick", None), getattr(snap, "estop", None), getattr(snap, "fault", None))
                self._seen_first_telem = True

            self._render_tick_delta(snap)
            self._render_live_readouts(snap)
            self._render_drive_status(snap)
            self._render_estop(snap)
            self._render_params_and_edit_state(snap)
            self._tx_lifetick_echo(snap)

            self._hb.inc("rx_telem", len(snaps))
            mode_v = str(getattr(snap, "mode", ""))
            estop_v = bool(getattr(snap, "estop", False))
            fault_v = bool(getattr(snap, "fault", False))
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
            if self._selected_axis:
                self._hb.set("axis", self._selected_axis)
            self._hb.emit(log)
        except Exception:
            log.exception("HiP poll_once crashed (continuing).")

    # ---------- render logic ----------

    def _tx_lifetick_echo(self, snap: TelemetrySnapshot) -> None:
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict) or not axes:
            return

        for axis_id, ax in axes.items():
            try:
                v = int(getattr(ax, "device_tick", 0)) & 0xFFFF
            except Exception:
                v = 0

            prev = self._last_lifetick_echo_sent.get(axis_id)
            if prev is not None and int(prev) == v:
                continue

            self._last_lifetick_echo_sent[axis_id] = v
            self.intent_out.publish_intent(EchoLifeTick(axis_id=axis_id, value=v, hip_id=self._hip_id))

    def _render_drive_status(self, snap: TelemetrySnapshot) -> None:
        if decode_drive_status is None:
            # Avoid hard crash if import path differs.
            return

        axis_id = self._selected_axis or self._fixed_axis
        if not axis_id:
            for w in (self._txt_main_amp_status, self._txt_slave_amp_status, self._txt_hdr_banner_left, self._txt_hdr_banner_right):
                if w is not None:
                    w.setText("")
            self._set_led_by_name("dotHdrOnline", state=None)
            self._set_led_by_name("dotHdrReady", state=None)
            self._set_led_by_name("dotHdrFbt", state=None)
            self._set_led_by_name("dotHdrBrake1", state=None)
            self._set_led_by_name("dotHdrBrake2", state=None)
            return

        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return
        ax = axes.get(axis_id)
        if ax is None:
            return

        main_word = int(getattr(ax, "status_word", 0) or 0)
        slave_word = int(getattr(ax, "guide_status_word", 0) or 0)

        main = decode_drive_status(main_word)
        slave = decode_drive_status(slave_word)

        if self._txt_main_amp_status is not None:
            self._txt_main_amp_status.setText(main.summary())
        if self._txt_slave_amp_status is not None:
            self._txt_slave_amp_status.setText(slave.summary())

        age = int(getattr(ax, "lifetick_age", 0) or 0)

        # Header banner: EsState derived from EStopStatus word (ladder: ESTOP->IDLE->ARMED->READY)
        word = _parse_estop_word_from_snapshot(snap)
        # ensure banner grace uses the correct taster rising edge
        taster_banner = bool(decode_estop_word(int(word) & 0xFFFFFFFF).get("taster", False))
        self._update_taster_edge(axis_id, taster_banner)
        estate = self._banner_estate_from_word(axis_id=axis_id, word=word)
        self._apply_banner_estate(estate)

        # Header ONLINE dot should represent the *link/connection* to Core/PLC telemetry.
        # 30 is an empirically-derived threshold to allow for some jitter but still indicate staleness reasonably quickly.
        # 500 is a sanity cap to avoid showing "good" for wildly stale telemetry 
        # (e.g. if lifetick_age is erroneously large due to a bug or overflow).
        # both numbers are somewhat arbitrary and should be adjusted based on real-world experience.
        online_state = "good" if (age <= 500) and (age > 30) else "bad"

        estop_word = int(getattr(snap, "estop_status_word", 0) or 0)
        estop_logical = decode_estop_word(estop_word)

        taster = bool(estop_logical.get("taster", False))
        ready = bool(estop_logical.get("ready", False))

        self._update_taster_edge(axis_id, taster)

        fbt_state = "good" if taster else "warn"
        ready_state = "good" if ready else "warn"

        brk1_raw = bool(estop_logical.get("brk1_ok", False))
        brk2_raw = bool(estop_logical.get("brk2_ok", False))

        brk1_ok = self._brake_ok_display(brk_ok_raw=brk1_raw, taster=taster, axis_id=axis_id)
        brk2_ok = self._brake_ok_display(brk_ok_raw=brk2_raw, taster=taster, axis_id=axis_id)

        brk1_state = "good" if brk1_ok else "bad"
        brk2_state = "good" if brk2_ok else "bad"

        self._set_led_by_name("dotHdrOnline", state=online_state)
        self._set_led_by_name("dotHdrReady", state=ready_state)
        self._set_led_by_name("dotHdrFbt", state=fbt_state)
        self._set_led_by_name("dotHdrBrake1", state=brk1_state)
        self._set_led_by_name("dotHdrBrake2", state=brk2_state)


    
    def _on_diag_resync_clicked(self) -> None:
        """Request a legacy ReSync pulse and clear local cut markers.

        If an axis is selected/attached we send an axis-scoped pulse.
        If no axis is attached we still send a *global* pulse (axis_id=""),
        which Core will translate into a one-shot CommandFrame.resync for all devices.
        """
        axis_id = (self._selected_axis or self._fixed_axis or "").strip()
        hip_id = str(getattr(self, "hip_id", "") or getattr(self, "_hip_id", "") or "")

        # Propagate to Core -> DenSi/PLC downlink.
        try:
            intent = RequestResync(axis_id=axis_id, hip_id=hip_id)
            if hasattr(self.intent_out, "publish_intent"):
                self.intent_out.publish_intent(intent)  # type: ignore[attr-defined]
            elif hasattr(self.intent_out, "send_intent"):
                self.intent_out.send_intent(intent)  # type: ignore[attr-defined]
            else:
                raise AttributeError("IntentOut has no publish_intent/send_intent")
            log.info("sent RequestResync axis_id=%r hip_id=%r", axis_id, hip_id)
        except Exception:
            log.exception("failed to send RequestResync axis_id=%r", axis_id)

        # Clear local cut markers (UI side). If no axis is attached, clear all.
        if axis_id:
            self._cut_valid_by_axis[axis_id] = False
            self._cut_time_by_axis.pop(axis_id, None)
            self._prev_estop_by_axis[axis_id] = bool(getattr(self, "_prev_estop_by_axis", {}).get(axis_id, False))
        else:
            self._cut_valid_by_axis.clear()
            self._cut_time_by_axis.clear()

        for w in (self._txt_cut_time, self._txt_cut_pos, self._txt_cut_vel, self._txt_posdiff):
            if w is not None:
                w.setText("--")

    def _render_live_readouts(self, snap: TelemetrySnapshot) -> None:
        """Render position/velocity/current/temp into txt_* fields (read-only)."""
        axis_id = self._selected_axis or self._fixed_axis
        if not axis_id:
            for w in (self._txt_pos, self._txt_vel, self._txt_amp, self._txt_temp):
                if w is not None:
                    w.setText("--")
            return

        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return
        ax = axes.get(axis_id)
        if ax is None:
            return

        try:
            pos = float(getattr(ax, "pos", 0.0) or 0.0)
        except Exception:
            pos = 0.0
        try:
            vel = float(getattr(ax, "vel", 0.0) or 0.0)
        except Exception:
            vel = 0.0

        params = getattr(snap, "params", {}) or {}
        if not isinstance(params, dict):
            params = {}

        def _pf(key: str, default: float) -> float:
            try:
                return float(params.get(key, default))
            except Exception:
                return float(default)

        amp = _pf("ActCur", _pf("Amp", 0.0))
        tmp = _pf("Temp", 20.0)

        # Fallback to raw PLC token dictionaries if present
        try:
            raw = getattr(snap, "plc_uplink_fields", None)
            if isinstance(raw, dict):
                if "ActCurUI" in raw and ("ActCur" not in params):
                    amp = float(raw.get("ActCurUI", amp))
                if "CabTemperatureUI" in raw and ("Temp" not in params):
                    tmp = float(raw.get("CabTemperatureUI", tmp))
        except Exception:
            pass

        if self._txt_pos is not None:
            self._txt_pos.setText(f"{pos:.2f} m")
        if self._txt_vel is not None:
            self._txt_vel.setText(f"{vel:.2f} m/s")
        if self._txt_amp is not None:
            self._txt_amp.setText(f"{int(round(amp))} A")
        if self._txt_temp is not None:
            self._txt_temp.setText(f"{int(round(tmp))}°")

        # --- Cut marker readouts 
        try:
            params = getattr(snap, "params", {}) or {}
            if not isinstance(params, dict):
                params = {}
            cut_pos = float(params.get("CutPos", 0.0) or 0.0)
            cut_vel = float(params.get("CutVel", 0.0) or 0.0)
            posdiff = float(params.get("PosDiffFor", 0.0) or 0.0)
            cur_estop = bool(getattr(snap, "estop", False))
            if not(cur_estop) :
                if self._txt_cut_pos is not None:
                    self._txt_cut_pos.setText('--')
                if self._txt_cut_vel is not None:
                    self._txt_cut_vel.setText('--')
                if self._txt_posdiff is not None:
                    self._txt_posdiff.setText('--')
            else:
                if self._txt_cut_pos is not None:
                    self._txt_cut_pos.setText(f"{cut_pos:.2f} m")
                if self._txt_cut_vel is not None:
                    self._txt_cut_vel.setText(f"{cut_vel:.2f} m/s")
                if self._txt_posdiff is not None:
                    self._txt_posdiff.setText(f"{posdiff:.2f} m")
            tail = getattr(snap, "plc_uplink_tail", {}) or {}
#            if not isinstance(tail, dict):
#                tail = {}

            # Time token: prefer DenSi preformatted UI text, else fall back to PLC tail[0] SystemTime.
            #t_tok = str(params.get("ui_cut_time_text", "") or "")
            #if not t_tok:
            t_tok = str(tail.get("SystemTime", "") or "kk")
            if self._txt_cut_time is not None:
                self._txt_cut_time.setText(t_tok if t_tok != "" else "--")

        except Exception:
            pass

        # --- slider indicators ---
        vel_max = float(params.get("VelMax", 0.0) or 0.0)
        if vel_max <= 0.0:
            vel_max = 1.0
        # commanded speed is provided by core as AxisTelemetry.vel_cmd (fallback: measured vel)
        vel_cmd = float(getattr(ax, "vel_cmd", vel) if ax is not None else vel)
        if self._sld_vel_cmd is not None:
            scale = 1000.0  # m/s -> mm/s
            self._sld_vel_cmd.blockSignals(True)
            self._sld_vel_cmd.setMinimum(int(round(-vel_max * scale)))
            self._sld_vel_cmd.setMaximum(int(round(+vel_max * scale)))
            self._sld_vel_cmd.setValue(int(round(vel_cmd * scale)))
            self._sld_vel_cmd.blockSignals(False)

        user_min = float(params.get("UserMin", 0.0) or 0.0)
        user_max = float(params.get("UserMax", 0.0) or 0.0)
        if user_max < user_min:
            user_min, user_max = user_max, user_min
        if self._sld_limit_range is not None:
            scale = 1000.0  # m -> mm
            self._sld_limit_range.blockSignals(True)
            self._sld_limit_range.setMinimum(int(round(user_min * scale)))
            self._sld_limit_range.setMaximum(int(round(user_max * scale)))
            self._sld_limit_range.setValue(int(round(pos * scale)))
            self._sld_limit_range.blockSignals(False)


        # --- guider slider indicators (mirror axis sliders) ---
        # limits derived from guider params (PosMin/PosMax), position from GuidePosIst if available
        g_pos_min = float(params.get("PosMin", 0.0) or 0.0)
        g_pos_max = float(params.get("PosMax", 0.0) or 0.0)
        if g_pos_max < g_pos_min:
            g_pos_min, g_pos_max = g_pos_max, g_pos_min

        # Guider position: prefer decoded param, fallback to raw PLC uplink field if present
        g_pos = float(params.get("GuidePosIst", 0.0) or 0.0)
        try:
            raw = getattr(snap, "plc_uplink_fields", None)
            if (g_pos == 0.0) and isinstance(raw, dict) and ("GuidePosIstUI" in raw):
                g_pos = float(raw.get("GuidePosIstUI", "0") or 0.0)
        except Exception:
            pass

        if self._sld_guider_range is not None:
            scale = 1000.0  # m -> mm
            self._sld_guider_range.blockSignals(True)
            self._sld_guider_range.setMinimum(int(round(g_pos_min * scale)))
            self._sld_guider_range.setMaximum(int(round(g_pos_max * scale)))
            self._sld_guider_range.setValue(int(round(g_pos * scale)))
            self._sld_guider_range.blockSignals(False)


        # Guider range readouts
        try:
            if self._txt_guider_range_min is not None:
                self._txt_guider_range_min.setText(f"{g_pos_min:.3f} m")
            if self._txt_guider_range_max is not None:
                self._txt_guider_range_max.setText(f"{g_pos_max:.3f} m")
            if self._txt_guider_range_val is not None:
                self._txt_guider_range_val.setText(f"{g_pos:.3f} m")
        except Exception:
            pass

        # Guider speed slider shows MEASURED guider speed (GuideIstSpeed),
        # but its range is derived from drum max rope speed VelMax + pitch + drum diameter:
        #   v_rope = omega * (pi*D)
        #   v_guide = omega * pitch
        # => v_guide = v_rope * pitch / (pi*D)
        drum_diam = 0.5  # meters
        pitch = float(params.get("Pitch", 0.0) or 0.0)  # meters per revolution
        denom = math.pi * drum_diam
        ratio = (pitch / denom) if (denom > 0.0 and pitch > 0.0) else 0.0

        g_vel_meas = float(params.get("GuideIstSpeed", 0.0) or 0.0)
        try:
            raw = getattr(snap, "plc_uplink_fields", None)
            if (g_vel_meas == 0.0) and isinstance(raw, dict) and ("GuideIstSpeedUI" in raw):
                g_vel_meas = float(raw.get("GuideIstSpeedUI", "0") or 0.0)
        except Exception:
            pass

        g_vel_max = abs(vel_max) * ratio
        if g_vel_max <= 0.0:
            g_vel_max = 1.0  # keep slider usable even if pitch not configured

        # clamp displayed value into range for slider
        if g_vel_meas > g_vel_max:
            g_vel_meas = g_vel_max
        elif g_vel_meas < -g_vel_max:
            g_vel_meas = -g_vel_max

        if self._sld_guider_speed is not None:
            scale = 1000.0  # m/s -> mm/s
            self._sld_guider_speed.blockSignals(True)
            self._sld_guider_speed.setMinimum(int(round(-g_vel_max * scale)))
            self._sld_guider_speed.setMaximum(int(round(+g_vel_max * scale)))
            self._sld_guider_speed.setValue(int(round(g_vel_meas * scale)))
            self._sld_guider_speed.blockSignals(False)


        # Guider speed readout (measured)
        try:
            if self._txt_guider_speed is not None:
                self._txt_guider_speed.setText(f"{g_vel_meas:.3f} m/s")
        except Exception:
            pass

    def _render_tick_delta(self, snap: TelemetrySnapshot) -> None:
        """Render legacy TimeTick into txt_tick (delta of device_tick)."""
        if self._txt_tick is None:
            return

        axis_id = self._selected_axis or self._fixed_axis
        if not axis_id:
            self._txt_tick.setText("--")
            self._prev_device_tick = None
            return

        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            log.info("HiP tick: snap.axes not dict (%s) -> %r", type(axes).__name__, axes)
            self._txt_tick.setText("--")
            self._prev_device_tick = None
            return

        ax = axes.get(axis_id)
        if ax is None:
            self._txt_tick.setText("--")
            self._prev_device_tick = None
            return

        cur_raw = getattr(ax, "device_tick", 0)
        try:
            cur = int(cur_raw)
        except Exception:
            log.info("HiP tick: axis %s device_tick not int-coercible: %r", axis_id, cur_raw)
            self._txt_tick.setText("--")
            self._prev_device_tick = None
            return

        delta, new_prev = compute_time_tick(self._prev_device_tick, cur)
        self._txt_tick.setText(str(delta))
        self._prev_device_tick = new_prev

    def _render_estop(self, snap: TelemetrySnapshot) -> None:
        word = int(getattr(snap, "estop_status_word", 0))
        logical = decode_estop_word(word)

        if bool(logical.get("schluessel1", False)):
            profile = "schluessel1"
        elif bool(logical.get("schluessel2", False)):
            profile = "schluessel2"
        else:
            profile = "integrated"

        if profile == "schluessel1":
            active_keys = {
                "master",
                "estop1", "estop2",
                "steuerwort",
                "kw30_ok",
                "brk1_ok",
                "sps_ok",
                "brk2kb_ok",
                "pos_win", "vel_win", "endlage",
            }
        elif profile == "schluessel2":
            active_keys = {
                "master", "guider",
                "estop1", "estop2",
                "steuerwort",
                "kw30_ok", "kw05_ok",
                "brk1_ok", "brk2_ok",
                "dcs_ok", "sps_ok",
                "brk2kb_ok",
                "pos_win", "vel_win", "endlage",
            }
        else:
            active_keys = set(ESTOP_SPECS.keys())

        if self.ui.btn_estop_reset:
            self.ui.btn_estop_reset.setEnabled(bool(logical.get("reset_able", False)))

        for key, cb in getattr(self, "_estop_checks", {}).items():
            v = bool(logical.get(key, False))
            cb.setChecked(v)
            f = cb.font()
            f.setBold(key in active_keys)
            cb.setFont(f)

        # Brake dots should match header brake logic:
        # - BRK1/BRK2: equivalence with taster + grace window
        # - BRK2KB: cable OK (normal logic, independent of taster)
        taster = bool(logical.get("taster", False))
        axis_id = self._selected_axis or self._fixed_axis
        if (not axis_id) or (axis_id == NOT_ATTACHED):
            try:
                axes = getattr(snap, "axes", {}) or {}
                axis_id = next(iter(axes.keys()))
            except Exception:
                axis_id = "X"

        for spec in ESTOP_SPECS.values():
            if not spec.dot:
                continue
            v = bool(logical.get(spec.key, False))

            if spec.key in ("brk1_ok", "brk2_ok"):
                disp_ok = self._brake_ok_display(brk_ok_raw=v, taster=taster, axis_id=axis_id)
                state = "good" if disp_ok else "bad"

            elif spec.key == "brk2kb_ok":
                state = "good" if v else "bad"

            elif spec.key in ESTOP_CAUSE_KEYS:
                state = "bad" if v else "good"
            elif spec.key in ESTOP_OK_KEYS:
                state = "good" if v else "bad"
            else:
                state = "warn" if v else None

            self._set_led_by_name(spec.dot, state=state)

    # ---------- axis selection / claims ----------

    def _update_axis_combo(self, snap: TelemetrySnapshot) -> None:
        if self._cmb_axis is None:
            return
        axes = getattr(snap, "axes", None)
        if axes is None:
            return
        if not isinstance(axes, dict):
            log.info("HiP axis discovery: snap.axes not dict (%s) -> %r", type(axes).__name__, axes)
            return

        axis_ids = sorted(list(axes.keys()))
        # Always include sentinel at top so pooled HiPs can remain unattached.
        items = [NOT_ATTACHED] + axis_ids

        cur = self._cmb_axis.currentText().strip()
        existing = [self._cmb_axis.itemText(i) for i in range(self._cmb_axis.count())]

        # If the list didn't change, just keep/repair selection.
        if existing == items:
            if self._fixed_axis and (self._fixed_axis in axis_ids):
                if cur != self._fixed_axis:
                    self._cmb_axis.setCurrentText(self._fixed_axis)
                return
            if cur not in items:
                self._cmb_axis.setCurrentText(NOT_ATTACHED)
            return

        self._cmb_axis.blockSignals(True)
        try:
            self._cmb_axis.clear()
            self._cmb_axis.addItems(items)

            if self._fixed_axis and (self._fixed_axis in axis_ids):
                self._cmb_axis.setCurrentText(self._fixed_axis)
                self._fixed_axis_applied = True
                if self._lock_axis_combo:
                    self._cmb_axis.setEnabled(False)
            else:
                # Pool mode: do NOT auto-attach. Default to NotAttached unless user already selected a valid axis.
                if self._selected_axis and (self._selected_axis in axis_ids):
                    self._cmb_axis.setCurrentText(self._selected_axis)
                else:
                    self._cmb_axis.setCurrentText(NOT_ATTACHED)
        finally:
            self._cmb_axis.blockSignals(False)

    def _on_axis_selected(self, axis_id: str) -> None:
        axis_id = (axis_id or "").strip()

        # Sentinel / detach
        if (not axis_id) or (axis_id == NOT_ATTACHED):
            if self._selected_axis:
                self.intent_out.publish_intent(ReleaseAxis(axis_id=self._selected_axis, hip_id=self._hip_id))
            self._selected_axis = ""
            self._set_attach_ui_state(attached=bool(self._fixed_axis))
            return

        # Switch attach
        if self._selected_axis and self._selected_axis != axis_id:
            self.intent_out.publish_intent(ReleaseAxis(axis_id=self._selected_axis, hip_id=self._hip_id))

        self.intent_out.publish_intent(ClaimAxis(axis_id=axis_id, hip_id=self._hip_id))
        self._selected_axis = axis_id
        self._set_attach_ui_state(attached=True)
