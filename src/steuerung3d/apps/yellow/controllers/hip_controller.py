# src/steuerung3d/apps/yellow/controllers/hip_controller.py
"""HiP (operator-side HMI) controller.

This module binds a Yellow .ui window to HiP behavior:
- receive TelemetrySnapshot (UDP) from core
- render per-axis state, E-Stop chain, and drive status
- send operator Intents back to core (enable/jog, parameter editing, resync, etc.)

Design goal: keep UI plumbing localized and keep runtime logic in poll_once.
"""

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
    ReleaseAxis,
    RequestEstopReset,
    RequestResync,
)
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.estop_bits import (
    ESTOP_SPECS,
    decode_estop_word,
)
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat
from steuerung3d.util.tick import compute_time_tick
from steuerung3d.util.ratelimit import rl_log_exc

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter  # type: ignore
except Exception:  # pragma: no cover
    StatusEmitter = None  # type: ignore

from .bindings import YellowBindings
from .ports import IntentOut, TelemetryIn
from .param_txn import ParamEditTxnClient
from .widget_cache import WidgetCache
from .ui_watchdog import PerfWatchdog
from .ui_contract import log_missing_optional_once
from .ui_update import set_checked, set_enabled, set_state_by_object_name, set_state_property, set_text, update_slider
from .ui_panel_state import clear_line_edits, neutralize_dots, uncheck_checkboxes
from .ui_estop import (
    age_to_online_state,
    compute_estop_dot_states,
    compute_header_estop_dot_states,
    infer_estop_profile,
    active_estop_keys_for_profile,
)
from .ui_banner import BANNER_COLORS, derive_banner_estate_from_word
from .ui_format import fmt_f_unit, fmt_i_unit
from .yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS, LIMIT_WIDGETS as _LIMIT_WIDGETS

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

# Axis selection sentinel for pooled HiP panels
NOT_ATTACHED = "NotAttached"

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
        return derive_banner_estate_from_word(
            int(word),
            within_brake_grace=lambda: self._within_banner_brake_grace(axis_id),
        )

    def _apply_banner_estate(self, estate: str) -> None:
        bg, fg = BANNER_COLORS.get(estate, ("#F9E547", "#000000"))
        for w in (self._txt_hdr_banner_left, self._txt_hdr_banner_right):
            if w is None:
                continue
            set_text(w, estate)
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
        """Bind widgets, wire signals, and initialize controller state.

        HiP is the *operator-side* HMI:
          - consumes TelemetrySnapshot (UDP) from core_udp_service
          - emits Intents (UDP) back to core_udp_service
          - drives all parameter editing (DenSi is device-side echo)

        Keep this initializer focused on wiring and local bookkeeping.
        All runtime work happens in :meth:`poll_once`.
        """
        self.ui = YellowBindings.from_window(self.win)

        # --- UI elements (widget lookup) ---
        self._init_widget_refs()

        # --- Observability (logging + optional supervisor heartbeat) ---
        self._init_observability()

        # --- Parameter edit & transactional intents bookkeeping ---
        # Must be initialized before _init_axis_selection(): the unattached UI
        # reset path may touch param-transaction state.
        self._init_param_txn_state()

        # --- Axis attachment / pooled UI behaviour ---
        self._init_axis_selection()

        # --- Wire signals (buttons, combo-box, etc.) ---
        self._wire_signals()

        # Validators for numeric parameter fields
        self._init_param_inputs()

        # Parameter UI starts locked until a ParamEditBegin happens.
        self._apply_param_ui_state(edit_active=False, edit_group="")

        # Paint an explicit startup state (unknown dots, no tick, etc.)
        self._reset_ui_startup()

    # -------------------------------------------------------------------------
    # Initialization helpers
    # -------------------------------------------------------------------------

    def _init_widget_refs(self) -> None:
        """Find and store all widgets we touch frequently.

        We keep the widget lookups in one place so:
          - missing widgets are easy to diagnose
          - controller logic reads like controller logic (not like Qt plumbing)
        """

        # Cached widget lookup (prevents repeated findChild() in hot paths)
        self._wcache = WidgetCache(self.win)
        self._wd = PerfWatchdog(log, name='hi_p')
        # Estop diagnostics checkboxes (read-only in HiP).
        self._estop_checks: dict[str, QCheckBox] = {}
        for spec in ESTOP_SPECS.values():
            if not spec.checkbox:
                continue
            w = self.win.findChild(QCheckBox, spec.checkbox)
            if w is not None:
                w.setEnabled(False)
                self._estop_checks[spec.key] = w

        # Telemetry staleness bookkeeping
        self._seen_first_telem = False
        self._last_rx_ns: int | None = None
        self._timer: QTimer | None = None

        # Axis selection UI (only present in pooled HiP variants)
        self._cmb_axis: QComboBox | None = self.win.findChild(QComboBox, "cmb_axis")

        # Legacy tick delta display
        self._txt_tick: QLineEdit | None = self.win.findChild(QLineEdit, "txt_tick")

        # Live readouts
        self._txt_pos: QLineEdit | None = self.win.findChild(QLineEdit, "txt_pos")
        self._txt_vel: QLineEdit | None = self.win.findChild(QLineEdit, "txt_vel")
        self._txt_amp: QLineEdit | None = self.win.findChild(QLineEdit, "txt_amp")
        self._txt_temp: QLineEdit | None = self.win.findChild(QLineEdit, "txt_temp")

        # Cut markers (latched in core; rendered here)
        self._txt_cut_pos: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_pos")
        self._txt_cut_vel: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_vel")
        self._txt_cut_time: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_time")
        self._txt_posdiff: QLineEdit | None = self.win.findChild(QLineEdit, "txt_posdiff")

        # HiP must not show DenSi-only SafetyPLC Start button
        _esstart = self.win.findChild(QPushButton, "btnESStart")
        if _esstart is not None:
            _esstart.hide()
            _esstart.setEnabled(False)

        # Diagnostic ReSync button (present in some UI variants)
        self._btn_diag_resync: QPushButton | None = (
            self.win.findChild(QPushButton, "btnReSync")
            or self.win.findChild(QPushButton, "btnDiagResync")
        )

        # Sliders used as live indicators
        self._sld_vel_cmd: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldVelCmd")
        self._sld_limit_range: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldLimitRange")
        self._sld_guider_range: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldGuiderRange")
        self._sld_guider_speed: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldGuiderSpeed")

        # Guider readouts
        self._txt_guider_range_min: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeMin")
        self._txt_guider_range_max: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeMax")
        self._txt_guider_range_val: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeValue")
        self._txt_guider_speed: QLineEdit | None = (
            self.win.findChild(QLineEdit, "txtGuiderSpeed")
            or self.win.findChild(QLineEdit, "txtGuiderPos_2")  # legacy name
        )

        # Drive status fields (legacy text lines)
        self._txt_main_amp_status: QLineEdit | None = self.win.findChild(QLineEdit, "txtMainAmpStatus")
        self._txt_slave_amp_status: QLineEdit | None = self.win.findChild(QLineEdit, "txtSlaveAmpStatus")
        self._txt_hdr_banner_left: QLineEdit | None = self.win.findChild(QLineEdit, "txtHdrBannerLeft")
        self._txt_hdr_banner_right: QLineEdit | None = self.win.findChild(QLineEdit, "txtHdrBannerRight")

        # Tick delta bookkeeping (legacy 'TimeTick' display)
        self._prev_device_tick: int | None = None

        # Last EchoLifeTick sent per axis (avoid spamming duplicates)
        self._last_lifetick_echo_sent: dict[str, int] = {}

        # Non-fatal UI contract check (helps diagnose mismatched .ui variants)
        # Grouped by feature and logged once per process (DEBUG only).
        log_missing_optional_once(
            log,
            self._wcache,
            [
                (QWidget, "dotHdrOnline"),
                (QWidget, "dotHdrReady"),
                (QWidget, "dotHdrFbt"),
                (QWidget, "dotHdrBrake1"),
                (QWidget, "dotHdrBrake2"),
            ],
            context="hi_p:hdr_dots",
        )
        log_missing_optional_once(
            log,
            self._wcache,
            [
                (QLineEdit, "txt_tick"),
                (QLineEdit, "txt_pos"),
                (QLineEdit, "txt_vel"),
                (QLineEdit, "txt_amp"),
                (QLineEdit, "txt_temp"),
            ],
            context="hi_p:readouts",
        )

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

    def _init_axis_selection(self) -> None:
        """Initialize pooled axis selection / fixed-axis pinning."""
        self._selected_axis: str = ""
        self._fixed_axis: str = ""
        self._lock_axis_combo: bool = False
        self._fixed_axis_applied: bool = False

        if self._cmb_axis is not None:
            self._cmb_axis.currentTextChanged.connect(self._on_axis_selected)

        # Start in 'unattached' visual state for pooled HiP panels.
        self._modal_locked: bool = False
        self._modal_prev_enabled: dict[QWidget, bool] = {}
        self._modal_prev_tabbar_enabled: bool | None = None
        self._set_attach_ui_state(attached=False)

    def _init_param_txn_state(self) -> None:
        """Initialize parameter edit state and transactional resend bookkeeping."""
        # Qt-free transactional helper (req_id/session_id bookkeeping + resends)
        self._param_txn = ParamEditTxnClient(hip_id=self._hip_id)

        # Param commit observation dialog (Option A: show only after applied/timeout)
        self._pending_commit_req_id: str = ""
        self._pending_commit_group: str = ""
        self._pending_commit_values: dict[str, float] = {}
        self._commit_dialog_shown_for: set[str] = set()

        # Deadman (taster) edge tracking for brake handoff display grace.
        self._taster_prev: dict[str, bool] = {}
        self._taster_pressed_s: dict[str, float] = {}



    def _wire_signals(self) -> None:
        """Connect UI actions to intent transmissions."""
        # E-Stop reset is enabled via telemetry; start disabled
        if self.ui.btn_estop_reset is not None:
            self.ui.btn_estop_reset.clicked.connect(self._on_estop_reset)
            log.info("wired: btnEStopReset -> RequestEstopReset intent")
            set_enabled(self.ui.btn_estop_reset, False)
        else:
            log.warning("btnEStopReset not found in UI")

        if self._btn_diag_resync is not None:
            self._btn_diag_resync.clicked.connect(self._on_diag_resync_clicked)
            # Only enabled when attached + in core Mode.IDLE (poll_once enforces)
            self._btn_diag_resync.setEnabled(False)

        # Parameter buttons (axis-agnostic v0.1)
        self._wire_param_buttons()

    def _reset_ui_startup(self) -> None:
        """Paint a deterministic startup state (no stale visuals)."""
        self._set_all_estop_unknown()
        if self._txt_tick is not None:
            set_text(self._txt_tick, "--")
        self._prev_device_tick = None

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

    def _attached_axis(self) -> str:
        return (self._selected_axis or self._fixed_axis or "").strip()

    def _require_attached(self) -> str | None:
        axis = self._attached_axis()
        if not axis:
            return None
        return axis

    def _clear_text_fields_for_unattached(self) -> None:
        # Clear all line edits except tick.
        keep = [self._txt_tick] if self._txt_tick is not None else []
        clear_line_edits(self.win, keep=keep, text="")
        if self._txt_tick is not None:
            set_text(self._txt_tick, "--")
        self._prev_device_tick = None

        # Clear a few known header/status fields if present
        for w in (self._txt_main_amp_status, self._txt_slave_amp_status, self._txt_hdr_banner_left, self._txt_hdr_banner_right):
            if w is not None:
                set_text(w, "")

    def _set_attach_ui_state(self, *, attached: bool) -> None:
        """Unattached = dead panel (grey + empty). Attached = normal (telemetry drives values).

        Everything is disabled when unattached, except cmb_axis so the user can attach.
        """
        tabs = self.win.findChild(QTabWidget, "tabsMain")

        if tabs is not None:
            if not attached:
                set_enabled(tabs, False)
            else:
                # Modal lock overrides; don't re-enable while locked.
                if not self._modal_locked:
                    set_enabled(tabs, True)

        # Keep axis combo usable in pool mode, unless locked to fixed axis.
        if self._cmb_axis is not None:
            if self._lock_axis_combo and self._fixed_axis_applied:
                set_enabled(self._cmb_axis, False)
            else:
                set_enabled(self._cmb_axis, True)

        # Setup toggle should be greyed out when unattached.
        btn_setup = self._find_button("btnSetupToggle")
        btn_Mainampreset = self._find_button("btn_reset")
        if btn_Mainampreset is not None:
            set_enabled(btn_Mainampreset, bool(attached) and (not self._modal_locked))
        if btn_setup is not None:
            set_enabled(btn_setup, bool(attached) and (not self._modal_locked))

        # Recover disabled always for now.
        btn_rec = self._find_button("btnRecover")
        if btn_rec is not None:
            set_enabled(btn_rec, False)

        # ReSync button is only usable in Mode.IDLE (poll_once drives it).
        if self._btn_diag_resync is not None:
            set_enabled(self._btn_diag_resync, bool(attached) and (not self._modal_locked) and (str(self._last_mode).upper() == "IDLE") and (str(getattr(self, "_last_estate", "")).upper() == "IDLE"))

        # E-stop reset disabled when unattached (telemetry enables it when attached)
        if self.ui.btn_estop_reset is not None and not attached:
            set_enabled(self.ui.btn_estop_reset, False)

        if not attached:
            self._clear_text_fields_for_unattached()

            # Neutralize header dots
            neutralize_dots(self._set_dot, ("dotHdrOnline", "dotHdrReady", "dotHdrFbt", "dotHdrBrake1", "dotHdrBrake2"))

            # Neutralize estop dots and checkboxes (no stale state)
            neutralize_dots(self._set_dot, [s.dot for s in ESTOP_SPECS.values() if s.dot])
            uncheck_checkboxes(getattr(self, "_estop_checks", {}).values())
            # Ensure param edit UI is not in edit mode
            txn = getattr(self, "_param_txn", None)
            if txn is not None:
                try:
                    txn.reset_local()
                except Exception:
                    pass
            self._apply_param_ui_state(edit_active=False, edit_group="")

        else:
            # Restore param button availability to whatever our local state is
            self._apply_param_ui_state(edit_active=self._param_txn.local_edit_active, edit_group=self._param_txn.local_edit_group)

    def _set_dot(self, object_name: str, state) -> None:
        """Set a dot state using cached lookup when possible."""
        if not object_name:
            return
        try:
            wcache = getattr(self, "_wcache", None)
            if wcache is not None:
                ww = wcache.widget(object_name)
                if ww is not None:
                    set_state_property(ww, state)
                    return
        except Exception:
            pass
        set_state_by_object_name(self.win, object_name, state)

    def _set_all_estop_unknown(self) -> None:
        for spec in ESTOP_SPECS.values():
            if spec.dot:
                self._set_dot(spec.dot, "warn")

    def _mark_disconnected(self) -> None:
        if self._seen_first_telem:
            log.warning("telemetry stale/disconnected -> reverting E-Stop LEDs to UNKNOWN")
        self._seen_first_telem = False
        if self.ui.btn_estop_reset:
            set_enabled(self.ui.btn_estop_reset, False)
        self._set_all_estop_unknown()
        if self._txt_tick is not None:
            set_text(self._txt_tick, "--")
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
        try:
            return self._wcache.button(object_name)
        except Exception:
            w = self.win.findChild(QPushButton, object_name)
            return w if isinstance(w, QPushButton) else None

    def _find_line_edit(self, object_name: str) -> QLineEdit | None:
        try:
            return self._wcache.line_edit(object_name)
        except Exception:
            w = self.win.findChild(QLineEdit, object_name)
            return w if isinstance(w, QLineEdit) else None

    def _init_param_inputs(self) -> None:
        loc = QLocale.system()
        for _grp, mapping in _PARAM_WIDGETS.items():
            for _key, obj_name in mapping.items():
                le = self._find_line_edit(obj_name)
                if le is None:
                    continue
                set_state_property(le, "true", prop="paramField")
                val = QDoubleValidator(-1.0e12, 1.0e12, 6, le)
                val.setLocale(loc)
                val.setNotation(QDoubleValidator.Notation.StandardNotation)
                le.setValidator(val)

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
            set_text(le, txt)
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
            set_text(le, txt)
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

        self._param_txn.start_local_edit(group)
        self._apply_param_ui_state(edit_active=True, edit_group=group)

        intent = self._param_txn.make_begin_intent(axis_id=axis, group=group)
        log.info(
            "tx intent: %s group=%s req_id=%s session=%s",
            type(intent).__name__,
            group,
            intent.req_id,
            intent.session_id,
        )
        self._param_txn.send(intent, group=group, kind="begin", publish=self.intent_out.publish_intent)

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

        intent = self._param_txn.make_write_intent(axis_id=axis, group=group, values=fixed)
        self._param_txn.send(intent, group=group, kind="write", publish=self.intent_out.publish_intent)

        # Track the commit observation (telemetry confirms via param_commit_* fields)
        self._pending_commit_req_id = intent.req_id
        self._pending_commit_group = group
        self._pending_commit_values = dict(fixed)

        self._param_txn.end_local_edit()
        self._apply_param_ui_state(edit_active=False, edit_group="")

    def _tx_param_cancel(self, group: str) -> None:
        axis = self._require_attached()
        if axis is None:
            return
        intent = self._param_txn.make_cancel_intent(axis_id=axis, group=group)
        self._param_txn.send(intent, group=group, kind="cancel", publish=self.intent_out.publish_intent)

        self._param_txn.end_local_edit()
        self._apply_param_ui_state(edit_active=False, edit_group="")

    # ---------- HIP<->Core transactional helpers ----------

    def _handle_core_acks(self, snap: TelemetrySnapshot) -> None:
        removed = self._param_txn.handle_core_acks(getattr(snap, "core_acks", []) or [])
        for rid in removed:
            log.info("core ack: %s", rid)

        self._apply_param_ui_state(edit_active=self._param_txn.local_edit_active, edit_group=self._param_txn.local_edit_group)

    def _retry_pending(self, now_ns: int) -> None:
        events = self._param_txn.retry_pending(now_ns, publish=self.intent_out.publish_intent)
        for ev in events:
            if ev.action == "giveup":
                log.error("txn give up: %s after %s retries (%s)", ev.req_id, ev.retries, ev.intent_type)
            else:
                log.warning("txn resend: %s retry=%s %s", ev.req_id, ev.retries, ev.intent_type)

    def _is_group_busy(self, group: str) -> bool:
        return self._param_txn.is_group_busy(group)


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

        # Safety policy: do not allow starting (or committing) parameter edits once the
        # SafetyPLC ladder estate has progressed to ARMED/READY.
        # (Cancel stays available so the operator can exit an edit session.)
        estate = str(getattr(self, "_last_estate", "") or "").upper()
        edits_allowed = estate not in ("ARMED", "READY")

        if be is not None:
            be.setEnabled((not editing) and edits_allowed)
        if bw is not None:
            bw.setEnabled(bool(editing) and edits_allowed)
        if bc is not None:
            bc.setEnabled(bool(editing))

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

        freeze_group = self._param_txn.local_edit_group if self._param_txn.local_edit_active else ""

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
                set_text(le, txt)
                le.blockSignals(was)

        try:
            self._render_limit_fields({k: float(params[k]) for k in ("HardMin", "UserMin", "UserMax", "HardMax") if k in params})
        except Exception:
            pass

    def _render_params_and_edit_state(self, snap: TelemetrySnapshot) -> None:
        self._render_params_from_telemetry(snap)
        self._maybe_show_param_commit_dialog(snap)

        if self._param_txn.local_edit_active:
            self._apply_param_ui_state(edit_active=True, edit_group=self._param_txn.local_edit_group)
            return

        now_ns = time.monotonic_ns()
        edit_active, edit_group = self._param_txn.effective_remote_edit_state(
            remote_active=bool(getattr(snap, "param_edit_active", False)),
            remote_group=str(getattr(snap, "param_edit_group", "") or ""),
            now_ns=now_ns,
        )
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
            rl_log_exc("hip.status.emit", "HiP status emission failed", logger=log)


    # ---------- polling ----------

    def start_polling(self, *, period_ms: int = 50) -> None:
        t = QTimer(self.win)
        t.setInterval(period_ms)
        t.timeout.connect(self.poll_once)
        t.start()
        self._timer = t
    def poll_once(self) -> None:
        with self._wd.tick():
            snaps = self.telemetry_in.drain_telemetry(limit=50)
            self._wd.mark('rx')
            now_ns = time.monotonic_ns()

            self._retry_pending(now_ns)
            self._wd.mark('retry')

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
            self._wd.mark('acks')
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
                self._wd.mark('render')

                self._hb.inc("rx_telem", len(snaps))
                mode_v = str(getattr(snap, "mode", ""))
                estop_v = bool(getattr(snap, "estop", False))
                fault_v = bool(getattr(snap, "fault", False))
                # Cache for status emitter and UI gating
                self._last_mode = mode_v
                self._last_estop = estop_v
                self._last_fault = fault_v

                # Determine SafetyPLC ladder state (banner estate) from EStopStatus word.
                try:
                    axis_id_for_estate = (self._selected_axis or self._fixed_axis or "").strip()
                    if (not axis_id_for_estate) or (axis_id_for_estate == NOT_ATTACHED):
                        axes_map = getattr(snap, "axes", {}) or {}
                        if isinstance(axes_map, dict) and axes_map:
                            axis_id_for_estate = next(iter(axes_map.keys()))
                    word = _parse_estop_word_from_snapshot(snap)
                    self._last_estate = self._banner_estate_from_word(axis_id=axis_id_for_estate or "X", word=word)
                except Exception:
                    self._last_estate = "ESTOP"

                # Fine-tuning: HiP ReSync is only allowed when the *system* is idle:
                # - Core rig mode is IDLE
                # - SafetyPLC ladder estate is IDLE (Schuetz OK, Taster released, no trip)
                if self._btn_diag_resync is not None:
                    try:
                        self._btn_diag_resync.setEnabled((mode_v.upper() == "IDLE") and (str(getattr(self, "_last_estate", "")).upper() == "IDLE") and (not self._modal_locked))
                    except Exception:
                        pass
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
                self._wd.mark('hb')
            except Exception:
                rl_log_exc("hip.poll_once", "HiP poll_once crashed (continuing).", logger=log, level="error")

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
                    set_text(w, "")
            self._set_dot("dotHdrOnline", None)
            self._set_dot("dotHdrReady", None)
            self._set_dot("dotHdrFbt", None)
            self._set_dot("dotHdrBrake1", None)
            self._set_dot("dotHdrBrake2", None)
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
            set_text(self._txt_main_amp_status, main.summary())
        if self._txt_slave_amp_status is not None:
            set_text(self._txt_slave_amp_status, slave.summary())

        age = int(getattr(ax, "lifetick_age", 0) or 0)

        # Header banner: EsState derived from EStopStatus word (ladder: ESTOP->IDLE->ARMED->READY)
        word = _parse_estop_word_from_snapshot(snap)
        # ensure banner grace uses the correct taster rising edge
        taster_banner = bool(decode_estop_word(int(word) & 0xFFFFFFFF).get("taster", False))
        self._update_taster_edge(axis_id, taster_banner)
        estate = self._banner_estate_from_word(axis_id=axis_id, word=word)
        self._apply_banner_estate(estate)

        # Header ONLINE dot should represent the *link/connection* to Core/PLC telemetry.
        # We treat "fresh" as green, "stale" as amber, and "offline" as red.
        #
        # age is the device lifetick age (in device ticks). Empirically:
        #   - <= 30 ticks: healthy/fresh updates (green)
        #   - 31..500 ticks: updates are stale but we still see life (amber)
        #   - > 500 ticks: effectively offline (red)
        #
        # Thresholds are intentionally conservative and can be tuned once we have
        # real-world timing with the full stack.
        online_state = age_to_online_state(age=float(age), good_max=30.0, warn_max=500.0)

        estop_word = int(getattr(snap, "estop_status_word", 0) or 0)
        estop_logical = decode_estop_word(estop_word)

        taster = bool(estop_logical.get("taster", False))
        ready = bool(estop_logical.get("ready", False))

        self._update_taster_edge(axis_id, taster)
        hdr = compute_header_estop_dot_states(
            taster=taster,
            ready=ready,
            brk1_raw=bool(estop_logical.get("brk1_ok", False)),
            brk2_raw=bool(estop_logical.get("brk2_ok", False)),
            brake_ok_display=lambda raw: self._brake_ok_display(
                brk_ok_raw=raw, taster=taster, axis_id=axis_id
            ),
        )

        fbt_state = hdr["dotHdrFbt"]
        ready_state = hdr["dotHdrReady"]
        brk1_state = hdr["dotHdrBrake1"]
        brk2_state = hdr["dotHdrBrake2"]

        self._set_dot("dotHdrOnline", online_state)
        self._set_dot("dotHdrReady", ready_state)
        self._set_dot("dotHdrFbt", fbt_state)
        self._set_dot("dotHdrBrake1", brk1_state)
        self._set_dot("dotHdrBrake2", brk2_state)



    def _on_diag_resync_clicked(self) -> None:
        """Request a legacy ReSync pulse and clear local cut markers.

        If an axis is selected/attached we send an axis-scoped pulse.
        If no axis is attached we still send a *global* pulse (axis_id=""),
        which Core will translate into a one-shot CommandFrame.resync for all devices.
        """
        # Fine-tuning guard: ReSync is only allowed when the *system* is idle.
        # System idle == Core mode IDLE AND SafetyPLC ladder estate IDLE (Taster released).
        mode_now = str(getattr(self, "_last_mode", "") or "").upper()
        estate_now = str(getattr(self, "_last_estate", "") or "").upper()
        if (mode_now != "IDLE") or (estate_now != "IDLE"):
            log.warning("ignored RequestResync (allowed only when system idle), mode=%s estate=%s", mode_now, estate_now)
            return

        axis_id = (self._selected_axis or self._fixed_axis or "").strip()
        hip_id = str(getattr(self, "hip_id", "") or getattr(self, "_hip_id", "") or "")

        # Propagate to Core -> DenSi/PLC downlink.
        try:
            intent = RequestResync(axis_id=axis_id, hip_id=hip_id)
            self.intent_out.publish_intent(intent)
            log.info("sent RequestResync axis_id=%r hip_id=%r", axis_id, hip_id)
        except Exception:
            log.exception("failed to send RequestResync axis_id=%r", axis_id)
        # Clear local cut markers (UI side)
        for w in (self._txt_cut_time, self._txt_cut_pos, self._txt_cut_vel, self._txt_posdiff):
            if w is not None:
                set_text(w, "--")

    def _render_live_readouts(self, snap: TelemetrySnapshot) -> None:
        """Render live readouts and slider indicators.

        Keep this method as a small orchestrator: each UI section gets its own
        helper, which makes future maintenance (and diffs) much easier.
        """
        axis_id = self._selected_axis or self._fixed_axis
        if not axis_id:
            self._render_axis_readouts_unattached()
            return

        ax = self._get_axis_telemetry(snap, axis_id)
        if ax is None:
            return

        params = self._params_dict(snap)

        pos, vel = self._read_axis_pos_vel(ax)
        amp, tmp = self._read_amp_and_temp(params, snap)

        self._apply_basic_readouts(pos=pos, vel=vel, amp=amp, temp=tmp)
        self._render_cut_marker_readouts(snap, params)
        self._render_axis_slider_indicators(ax=ax, pos=pos, vel_meas=vel, params=params)
        self._render_guider_indicators(params=params, snap=snap)

    # ---------------------------------------------------------------------
    # Live readouts helpers (UI-only; must never raise)
    # ---------------------------------------------------------------------

    def _render_axis_readouts_unattached(self) -> None:
        for w in (self._txt_pos, self._txt_vel, self._txt_amp, self._txt_temp):
            if w is not None:
                set_text(w, "--")

    def _get_axis_telemetry(self, snap: TelemetrySnapshot, axis_id: str):
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return None
        return axes.get(axis_id)

    def _params_dict(self, snap: TelemetrySnapshot) -> dict:
        params = getattr(snap, "params", {}) or {}
        return params if isinstance(params, dict) else {}

    def _read_axis_pos_vel(self, ax) -> tuple[float, float]:
        try:
            pos = float(getattr(ax, "pos", 0.0) or 0.0)
        except Exception:
            pos = 0.0
        try:
            vel = float(getattr(ax, "vel", 0.0) or 0.0)
        except Exception:
            vel = 0.0
        return pos, vel

    def _raw_uplink_float(self, snap: TelemetrySnapshot, key: str, default: float) -> float:
        """Best-effort float from raw PLC uplink fields."""
        try:
            raw = getattr(snap, "plc_uplink_fields", None)
            if isinstance(raw, dict) and key in raw:
                return float(raw.get(key, default) or default)
        except Exception:
            pass
        return float(default)

    def _raw_tail_token(self, snap: TelemetrySnapshot, key: str) -> str:
        try:
            tail = getattr(snap, "plc_uplink_tail", {}) or {}
            if isinstance(tail, dict):
                v = tail.get(key, "") or ""
                return str(v)
        except Exception:
            pass
        return ""

    def _read_amp_and_temp(self, params: dict, snap: TelemetrySnapshot) -> tuple[float, float]:
        """Return (amp, temp) using params with raw PLC fallbacks."""

        def _pf(key: str, default: float) -> float:
            try:
                return float(params.get(key, default))
            except Exception:
                return float(default)

        amp = _pf("ActCur", _pf("Amp", 0.0))
        tmp = _pf("Temp", 20.0)

        # Fallback to raw PLC token dictionaries if present
        if "ActCur" not in params:
            amp = self._raw_uplink_float(snap, "ActCurUI", amp)
        if "Temp" not in params:
            tmp = self._raw_uplink_float(snap, "CabTemperatureUI", tmp)

        return amp, tmp

    def _apply_basic_readouts(self, pos: float, vel: float, amp: float, temp: float) -> None:
        if self._txt_pos is not None:
            set_text(self._txt_pos, fmt_f_unit(pos, "m", ndigits=2))
        if self._txt_vel is not None:
            self._txt_vel.setText(f"{vel:.2f} m/s")
        if self._txt_amp is not None:
            set_text(self._txt_amp, fmt_i_unit(int(round(amp)), "A"))
        if self._txt_temp is not None:
            self._txt_temp.setText(f"{int(round(temp))}°")

    def _render_cut_marker_readouts(self, snap: TelemetrySnapshot, params: dict) -> None:
        """Update cut marker readouts (position/velocity/posdiff/time).

        These values are meaningful while in E-Stop. Historically the UI gated them
        using `snap.estop`. Some telemetry paths, however, may provide the E-Stop
        status only via the status word (the same one that drives dots/banner).
        To avoid confusing the operator, we gate cut markers using the *word* first,
        with `snap.estop` as a fallback.
        """
        try:
            cut_pos = float(params.get("CutPos", 0.0) or 0.0)
            cut_vel = float(params.get("CutVel", 0.0) or 0.0)
            posdiff = float(params.get("PosDiffFor", 0.0) or 0.0)

            # Prefer the decoded status word (same source as dots/banner).
            in_estop = bool(getattr(snap, "estop", False))
            try:
                word = _parse_estop_word_from_snapshot(snap)
                bits = decode_estop_word(int(word))
                in_estop = any(bool(bits.get(k, False)) for k in ("master", "slave", "network", "estop1", "estop2"))
            except Exception:
                pass

            # Final fallback: if the banner estate is ESTOP, treat it as estop.
            if not in_estop:
                estate = str(getattr(self, "_last_estate", "") or "").upper()
                if estate == "ESTOP":
                    in_estop = True

            if not in_estop:
                if self._txt_cut_pos is not None:
                    set_text(self._txt_cut_pos, "--")
                if self._txt_cut_vel is not None:
                    set_text(self._txt_cut_vel, "--")
                if self._txt_posdiff is not None:
                    set_text(self._txt_posdiff, "--")
            else:
                if self._txt_cut_pos is not None:
                    set_text(self._txt_cut_pos, fmt_f_unit(cut_pos, "m", ndigits=2))
                if self._txt_cut_vel is not None:
                    set_text(self._txt_cut_vel, fmt_f_unit(cut_vel, "m/s", ndigits=2))
                if self._txt_posdiff is not None:
                    set_text(self._txt_posdiff, fmt_f_unit(posdiff, "m", ndigits=2))

            # CutTime comes from DenSi/PLC tail token (SystemTime).
            # Policy: HiP does **not** freeze it; DenSi is authoritative for when it advances.
            t_tok = self._raw_tail_token(snap, "SystemTime")
            if self._txt_cut_time is not None:
                set_text(self._txt_cut_time, t_tok if t_tok else "--")
        except Exception:
            pass


    def _render_axis_slider_indicators(self, ax, pos: float, vel_meas: float, params: dict) -> None:
        """Update axis slider indicators (commanded vel and position within limits)."""
        # VelMax is used as slider range. Guard against invalid/zero values.
        try:
            vel_max = float(params.get("VelMax", 0.0) or 0.0)
        except Exception:
            vel_max = 0.0
        if vel_max <= 0.0:
            vel_max = 1.0

        # commanded speed is provided by core as AxisTelemetry.vel_cmd (fallback: measured vel)
        try:
            vel_cmd = float(getattr(ax, "vel_cmd", vel_meas) if ax is not None else vel_meas)
        except Exception:
            vel_cmd = vel_meas
        if self._sld_vel_cmd is not None:
            scale = 1000.0  # m/s -> mm/s
            update_slider(
                self._sld_vel_cmd,
                minimum=int(round(-vel_max * scale)),
                maximum=int(round(+vel_max * scale)),
                value=int(round(vel_cmd * scale)),
            )

        try:
            user_min = float(params.get("UserMin", 0.0) or 0.0)
        except Exception:
            user_min = 0.0
        try:
            user_max = float(params.get("UserMax", 0.0) or 0.0)
        except Exception:
            user_max = 0.0
        if user_max < user_min:
            user_min, user_max = user_max, user_min
        if self._sld_limit_range is not None:
            scale = 1000.0  # m -> mm
            update_slider(
                self._sld_limit_range,
                minimum=int(round(user_min * scale)),
                maximum=int(round(user_max * scale)),
                value=int(round(pos * scale)),
            )

    def _render_guider_indicators(self, params: dict, snap: TelemetrySnapshot) -> None:
        """Update guider range + speed readouts and sliders."""
        # limits derived from guider params (PosMin/PosMax), position from GuidePosIst if available
        try:
            g_pos_min = float(params.get("PosMin", 0.0) or 0.0)
        except Exception:
            g_pos_min = 0.0
        try:
            g_pos_max = float(params.get("PosMax", 0.0) or 0.0)
        except Exception:
            g_pos_max = 0.0
        if g_pos_max < g_pos_min:
            g_pos_min, g_pos_max = g_pos_max, g_pos_min

        # Guider position: prefer decoded param, fallback to raw PLC uplink field if present
        try:
            g_pos = float(params.get("GuidePosIst", 0.0) or 0.0)
        except Exception:
            g_pos = 0.0
        if g_pos == 0.0:
            g_pos = self._raw_uplink_float(snap, "GuidePosIstUI", g_pos)
        if self._sld_guider_range is not None:
            scale = 1000.0  # m -> mm
            update_slider(
                self._sld_guider_range,
                minimum=int(round(g_pos_min * scale)),
                maximum=int(round(g_pos_max * scale)),
                value=int(round(g_pos * scale)),
            )

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
        try:
            vel_max = float(params.get("VelMax", 0.0) or 0.0)
        except Exception:
            vel_max = 0.0
        if vel_max <= 0.0:
            vel_max = 1.0

        drum_diam = 0.5  # meters
        try:
            pitch = float(params.get("Pitch", 0.0) or 0.0)  # meters per revolution
        except Exception:
            pitch = 0.0

        denom = math.pi * drum_diam
        ratio = (pitch / denom) if (denom > 0.0 and pitch > 0.0) else 0.0

        try:
            g_vel_meas = float(params.get("GuideIstSpeed", 0.0) or 0.0)
        except Exception:
            g_vel_meas = 0.0
        if g_vel_meas == 0.0:
            g_vel_meas = self._raw_uplink_float(snap, "GuideIstSpeedUI", g_vel_meas)

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
            update_slider(
                self._sld_guider_speed,
                minimum=int(round(-g_vel_max * scale)),
                maximum=int(round(+g_vel_max * scale)),
                value=int(round(g_vel_meas * scale)),
            )

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
            set_text(self._txt_tick, "--")
            self._prev_device_tick = None
            return

        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            log.info("HiP tick: snap.axes not dict (%s) -> %r", type(axes).__name__, axes)
            set_text(self._txt_tick, "--")
            self._prev_device_tick = None
            return

        ax = axes.get(axis_id)
        if ax is None:
            set_text(self._txt_tick, "--")
            self._prev_device_tick = None
            return

        cur_raw = getattr(ax, "device_tick", 0)
        try:
            cur = int(cur_raw)
        except Exception:
            log.info("HiP tick: axis %s device_tick not int-coercible: %r", axis_id, cur_raw)
            set_text(self._txt_tick, "--")
            self._prev_device_tick = None
            return

        delta, new_prev = compute_time_tick(self._prev_device_tick, cur)
        self._txt_tick.setText(str(delta))
        self._prev_device_tick = new_prev
    def _render_estop(self, snap: TelemetrySnapshot) -> None:
        word = int(getattr(snap, "estop_status_word", 0))
        logical = decode_estop_word(word)

        profile = infer_estop_profile(logical)
        active_keys = active_estop_keys_for_profile(profile, ESTOP_SPECS.keys())
        profile_changed = (getattr(self, "_last_estop_profile", None) != profile)
        self._last_estop_profile = profile

        if self.ui.btn_estop_reset:
            self.ui.btn_estop_reset.setEnabled(bool(logical.get("reset_able", False)))

        # Sync read-only diagnostic checkboxes. Keep this cheap: only touch the UI if
        # something actually changed, and only re-bold the active profile keys when the
        # profile itself changes.
        for key, cb in getattr(self, "_estop_checks", {}).items():
            v = bool(logical.get(key, False))
            try:
                if cb.isChecked() != v:
                    cb.setChecked(v)
            except Exception:
                pass
            if profile_changed:
                try:
                    f = cb.font()
                    f.setBold(key in active_keys)
                    cb.setFont(f)
                except Exception:
                    pass

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

        states = compute_estop_dot_states(
            bits=logical,
            taster=taster,
            specs=ESTOP_SPECS.values(),
            brake_ok_display=lambda raw: self._brake_ok_display(
                brk_ok_raw=raw, taster=taster, axis_id=axis_id
            ),
        )
        for dot, state in states.items():
            self._set_dot(dot, state)


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
                    set_enabled(self._cmb_axis, False)
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
