# src/steuerung3d/apps/yellow/controllers/hip_controller.py
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QLocale, QTimer
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QLineEdit, QPushButton, QWidget, QMessageBox, QTabWidget

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
        "PosMin": "txtGPosMin_3",
        "PosMax": "txtGPosMax_2",
        "Pitch": "txtPitch_2",
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

        # Modal param edit lock bookkeeping
        self._modal_locked: bool = False
        self._modal_prev_enabled: dict[QWidget, bool] = {}
        self._modal_prev_tabbar_enabled: bool | None = None

        # After write/cancel, ignore remote edit flags briefly to avoid UI flicker
        self._ignore_remote_edit_until_ns: int = 0

        # Param commit observation dialog (Option A: show only after applied/timeout)
        self._pending_commit_req_id: str = ""
        self._pending_commit_group: str = ""
        self._pending_commit_values: dict[str, float] = {}
        self._commit_dialog_shown_for: set[str] = set()


        # HIP<->Core transactional param intents (best-effort reliability)
        self._req_seq: int = 0
        self._session_by_group: dict[str, str] = {}
        # req_id -> dict(intent=..., group=..., sent_ns=..., retries=...)
        self._pending_txn: dict[str, dict] = {}
        self._resend_after_ms: int = 250
        self._max_retries: int = 8

        # Local UI-driven edit state (do not depend on DenSi telemetry for gating)
        self._local_edit_group: str = ""
        self._local_edit_active: bool = False

        # (intentionally no duplicate state here)

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
                # NOTE: QSS selector uses string: paramField="true"
                le.setProperty("paramField", "true")
                # Numeric-only entry; parent the validator to the field so it stays alive.
                val = QDoubleValidator(-1.0e12, 1.0e12, 6, le)
                val.setLocale(loc)
                val.setNotation(QDoubleValidator.Notation.StandardNotation)
                le.setValidator(val)

                # Force initial polish so the style reacts immediately.
                le.style().unpolish(le)
                le.style().polish(le)
                le.update()

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
        """Enforce PosMin <= PosMax for guider group (clamp; do not swap)."""
        v = dict(values)
        if "PosMin" not in v or "PosMax" not in v:
            return v

        pos_min = float(v["PosMin"])
        pos_max = float(v["PosMax"])

        # Clamp so that PosMin <= PosMax without swapping (avoid surprising jumps).
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
        # Local gating first: unlock immediately
        self._local_edit_active = True
        self._local_edit_group = group
        self._apply_param_ui_state(edit_active=True, edit_group=group)

        # new edit session per press
        session_id = f"sess-{group}-{int(time.monotonic()*1000)}"
        self._session_by_group[group] = session_id
        req_id = self._next_req_id()

        intent = ParamEditBegin(group=group, req_id=req_id, session_id=session_id)
        log.info("tx intent: %s group=%s req_id=%s session=%s", type(intent).__name__, group, req_id, session_id)
        self._send_txn_intent(intent, group=group, kind="begin")

    def _tx_param_write(self, group: str) -> None:
        # Normalize locally so HIP fields reflect what is actually sent.
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
                        "The rule HardMax ≥ UserMax ≥ UserMin ≥ HardMin was enforced.\n\n"
                        + "\n".join(lines),
                    )

        session_id = self._ensure_session(group)
        req_id = self._next_req_id()
        intent = ParamWrite(group=group, values=fixed, req_id=req_id, session_id=session_id)
        log.info(
            "tx intent: %s group=%s req_id=%s session=%s keys=%s",
            type(intent).__name__,
            group,
            req_id,
            session_id,
            sorted(fixed.keys()),
        )
        self._send_txn_intent(intent, group=group, kind="write")

        # Remember this commit for modal dialog feedback once core observes applied/timeout
        self._pending_commit_req_id = req_id
        self._pending_commit_group = group
        self._pending_commit_values = dict(fixed)

        # End local edit session immediately (operator finished the group)
        self._local_edit_active = False
        self._local_edit_group = ""
        self._ignore_remote_edit_until_ns = time.monotonic_ns() + 800_000_000
        self._apply_param_ui_state(edit_active=False, edit_group="")

    def _tx_param_cancel(self, group: str) -> None:
        session_id = self._ensure_session(group)
        req_id = self._next_req_id()
        intent = ParamCancel(group=group, req_id=req_id, session_id=session_id)
        log.info("tx intent: %s group=%s req_id=%s session=%s", type(intent).__name__, group, req_id, session_id)
        self._send_txn_intent(intent, group=group, kind="cancel")

        # End local edit session immediately
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
        """Publish intent and remember it until core acks it via telemetry.core_acks."""
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

        # refresh UI state (enables edit again once busy clears)
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
        for info in self._pending_txn.values():
            if info.get("group") != group:
                continue
            # Only treat write/cancel as "busy" for UI disabling.
            if str(info.get("kind") or "") in ("write", "cancel"):
                return True
        return False

    # ----- modal lock helpers -----

    def _set_modal_param_lock(self, *, active: bool, group: str) -> None:
        """Lock the UI while editing one param group.

        Requirement: while editing a group, operator must not:
          - start editing another group
          - switch tabs
          - click other actions
        They can only finish the edit via Write or Cancel.
        """

        tabs = self.win.findChild(QTabWidget, "tabsMain")

        if active and not self._modal_locked:
            self._modal_prev_enabled = {}

            # Disable tab switching (but don't disable the whole QTabWidget, or it would
            # also disable the allowed children).
            if tabs is not None:
                self._modal_prev_tabbar_enabled = bool(tabs.tabBar().isEnabled())
                tabs.tabBar().setEnabled(False)

            # Disable all buttons + line edits first.
            for w in self.win.findChildren(QWidget):
                if isinstance(w, (QPushButton, QLineEdit)):
                    self._modal_prev_enabled[w] = bool(w.isEnabled())
                    w.setEnabled(False)

            # Re-enable only the active group's line edits and Write/Cancel.
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
            # Restore previous enabled states
            for w, was_enabled in list(self._modal_prev_enabled.items()):
                try:
                    w.setEnabled(bool(was_enabled))
                    if isinstance(w, QLineEdit):
                        w.style().unpolish(w)
                        w.style().polish(w)
                        w.update()
                except RuntimeError:
                    # Widget already deleted
                    pass
            self._modal_prev_enabled.clear()

            if tabs is not None and self._modal_prev_tabbar_enabled is not None:
                tabs.tabBar().setEnabled(bool(self._modal_prev_tabbar_enabled))
            self._modal_prev_tabbar_enabled = None

            self._modal_locked = False
    # ----- parameters: UI state reflection (axis-agnostic v0.1) -----

    def _set_param_group_enabled(self, group: str, enabled: bool) -> None:
        """Enable/disable the parameter line-edits for a group."""
        mapping = _PARAM_WIDGETS.get(group, {})
        for _key, obj_name in mapping.items():
            le = self._find_line_edit(obj_name)
            if le is None:
                continue
            le.setEnabled(bool(enabled))
            # Re-polish to ensure QSS (white/gray) applies immediately.
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
        """Reflect edit state onto HiP widget enable/disable.

        - Fields are editable only when their group's Edit was pressed (or DenSi reports edit mode).
        - While a transactional request for a group is pending, that group is 'busy' and all 3 buttons
          are disabled to avoid session races.
        """
        groups = ("pos", "vel", "filter", "guider")

        # Enforce "one group at a time" editing as a modal lock.
        self._set_modal_param_lock(active=bool(edit_active), group=str(edit_group or ""))

        if edit_active:
            # While editing one group, keep all other controls disabled.
            for g in groups:
                if g == edit_group:
                    busy = self._is_group_busy(g)
                    is_edit = True
                    self._set_param_group_enabled(g, bool(not busy))
                    self._set_param_button_state(g, editing=is_edit, busy=busy)
                else:
                    self._set_param_group_enabled(g, False)
                    # Force other groups disabled (prevents re-enabling after modal lock).
                    self._set_param_button_state(g, editing=False, busy=True)
            return

        for g in groups:
            busy = self._is_group_busy(g)
            self._set_param_group_enabled(g, False)
            self._set_param_button_state(g, editing=False, busy=busy)

    def _render_params_from_telemetry(self, snap: TelemetrySnapshot) -> None:
        """Update parameter text fields from telemetry.

        Important: do NOT overwrite the group currently being edited locally, and never overwrite
        the field that currently has focus.
        """
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
                if le is None:
                    continue
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
        self._render_params_from_telemetry(snap)

        # --- Option A: modal dialog once core observes applied/timeout ---
        self._maybe_show_param_commit_dialog(snap)

        # Local edit state has priority (UI should not depend on DenSi telemetry timing).
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
            QMessageBox.information(
                self.win,
                "Parameters applied",
                f"{group} parameters were applied (observed in telemetry).",
            )
        else:
            unmatched = list(getattr(snap, "param_commit_unmatched", []) or [])
            params = dict(getattr(snap, "params", {}) or {})
            want = dict(self._pending_commit_values or {})

            lines = [f"{group} parameters were not confirmed (timeout).", "", "Mismatches:"]
            for k in unmatched:
                w = want.get(k, "?")
                g = params.get(k, "<missing>")
                lines.append(f"- {k}: want {w}  got {g}")
            QMessageBox.warning(
                self.win,
                "Parameters not confirmed",
                "\n".join(lines),
            )

        # Clear pending commit so the next write can create a new one.
        self._pending_commit_req_id = ""
        self._pending_commit_group = ""
        self._pending_commit_values = {}

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

        # drive transactional resends even if telemetry is quiet
        self._retry_pending(now_ns)

        if not snaps:
            if self._last_rx_ns is not None:
                age_ms = (now_ns - self._last_rx_ns) / 1_000_000.0
                if age_ms >= float(self.stale_after_ms):
                    self._last_rx_ns = None
                    self._mark_disconnected()
            return

        snap = snaps[-1]
        self._last_rx_ns = now_ns

        # consume any core acks for transactional param intents
        self._handle_core_acks(snap)

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
