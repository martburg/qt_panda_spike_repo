"""Qt-free HiP engine (minimal seam).

Purpose: provide a stable place to compute attach-state enablement and banner
estate without changing controller behavior. This is used for shadow-mode
comparison before cutover.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from steuerung3d.core.intents import (
    ClaimAxis,
    EchoLifeTick,
    EnableAxis,
    JogAxis,
    JogCartesian,
    JogWinch,
    ReleaseAxis,
    RequestEstopReset,
    RequestResync,
    SmoothStop,
)
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.estop_bits import ESTOP_SPECS, decode_estop_word
from steuerung3d.util.tick import compute_time_tick

from ...domain.param_txn import ParamEditTxnClient, RetryEvent
from ...domain.ui_estop import age_to_online_state, infer_estop_profile
from ...domain.ui_banner import derive_banner_estate_from_word
from ...domain.ui_format import fmt_f_unit, fmt_i_unit
from ...domain.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS, LIMIT_WIDGETS as _LIMIT_WIDGETS
from ...domain.joy_motion_map import map_soll_speed_to_jog_winch
from .types import HipPresentationData

from .types import (
    HipAttachCombo,
    HipAttachInputs,
    HipAttachState,
    HipBannerInputs,
    HipParamAction,
    HipParamButtons,
    HipParamCommitDialog,
    HipParamGroup,
    HipParamUiState,
    HipState,
    HipStepInputs,
    HipStepResult,
    HipUiInputs,
)
from .viewmodel import (
    HipBannerState,
    HipCutMarkersState,
    HipDriveStatusState,
    HipEstopState,
    HipHeaderDots,
    HipReadoutsState,
    HipViewModel,
)

# NOTE: drive status decoder is optional.
try:
    from steuerung3d.protocol.drive_status import decode_drive_status  # type: ignore
except Exception:  # pragma: no cover
    decode_drive_status = None  # type: ignore


NOT_ATTACHED = "NotAttached"


class HipEngine:
    """Minimal HipEngine surface (shadow-mode only)."""

    def __init__(self, *, hip_id: str = "") -> None:
        self._param_txn = ParamEditTxnClient(hip_id=str(hip_id or ""))
        self._taster_prev: dict[str, bool] = {}
        self._taster_pressed_s: dict[str, float] = {}
        self.state = HipState()

    @staticmethod
    def _is_motion_intent(intent: object) -> bool:
        return isinstance(intent, (EnableAxis, JogAxis, JogWinch, JogCartesian, SmoothStop))

    def _gate_motion_intents(self, intents: Iterable[object], *, deadman: bool) -> list[object]:
        if bool(deadman):
            return list(intents)
        return [i for i in intents if not self._is_motion_intent(i)]

    def _claim_allowed(self, axis_id: str, now_ns: int, *, min_interval_ns: int = 500_000_000) -> bool:
        last = int(self.state.last_claim_attempt_ns_by_axis.get(axis_id, -10**18))
        if int(now_ns) - last < int(min_interval_ns):
            return False
        self.state.last_claim_attempt_ns_by_axis[axis_id] = int(now_ns)
        return True

    def _should_emit_speed(self, axis_id: str, speed: float, *, eps: float = 1e-3) -> bool:
        last = self.state.last_sent_speed_by_axis.get(axis_id)
        if last is None or abs(float(speed) - float(last)) > float(eps):
            self.state.last_sent_speed_by_axis[axis_id] = float(speed)
            return True
        return False

    @staticmethod
    def _get_claim_owner(snap: TelemetrySnapshot, axis_id: str) -> str:
        densis = getattr(snap, "densis", None)
        if isinstance(densis, dict):
            d = densis.get(axis_id)
            if d is not None:
                return str(getattr(d, "claimed_by_hip", "") or "")
        return ""

    def _update_taster_edge(self, axis_id: str, taster: bool, now_s: float) -> None:
        prev = self._taster_prev.get(axis_id, taster)
        if (not prev) and taster:
            self._taster_pressed_s[axis_id] = float(now_s)
        self._taster_prev[axis_id] = bool(taster)

    def _within_brake_grace(self, axis_id: str, now_s: float, grace_s: float) -> bool:
        t0 = self._taster_pressed_s.get(axis_id)
        if t0 is None:
            return False
        return (float(now_s) - float(t0)) <= float(grace_s)

    def compute_attach_state(self, inputs: HipAttachInputs) -> HipAttachState:
        attached = bool(inputs.attached)
        modal_locked = bool(inputs.modal_locked)
        last_mode = str(inputs.last_mode or "").upper()
        last_estate = str(inputs.last_estate or "").upper()

        # Preserve legacy behavior: when modal-locked and attached, do not
        # force tabs enabled/disabled.
        if attached and modal_locked:
            tabs_enabled: bool | None = None
        else:
            tabs_enabled = bool(attached) and (not modal_locked)

        setup_enabled = bool(attached) and (not modal_locked)
        main_amp_reset_enabled = bool(attached) and (not modal_locked)

        resync_enabled = (
            bool(attached)
            and (not modal_locked)
            and (last_mode == "IDLE")
            and (last_estate == "IDLE")
        )

        # Preserve legacy behavior: only force-disable when unattached.
        estop_reset_enabled: bool | None = None if attached else False

        return HipAttachState(
            attached=attached,
            tabs_enabled=tabs_enabled,
            setup_enabled=setup_enabled,
            main_amp_reset_enabled=main_amp_reset_enabled,
            resync_enabled=resync_enabled,
            estop_reset_enabled=estop_reset_enabled,
        )

    def compute_banner_estate(self, inputs: HipBannerInputs) -> str:
        return derive_banner_estate_from_word(
            int(inputs.estop_word),
            within_brake_grace=lambda: bool(inputs.within_brake_grace),
        )

    def step(self, inputs: HipStepInputs) -> HipStepResult:
        snap = inputs.snap
        ui = inputs.ui
        hip_id = str(inputs.hip_id or "")
        joy_in = inputs.joy if isinstance(inputs.joy, JoyState) else JoyState()
        self.state.joy = JoyState(
            deadman=bool(getattr(joy_in, "deadman", False)),
            select_hip=bool(getattr(joy_in, "select_hip", False)),
            soll_speed=clamp_soll_speed(getattr(joy_in, "soll_speed", 0.0)),
        )
        if getattr(self._param_txn, "hip_id", "") != hip_id:
            self._param_txn.hip_id = hip_id

        axes = getattr(snap, "axes", None)
        axes = axes if isinstance(axes, dict) else {}
        axis_ids = sorted(list(axes.keys()))

        ui_axis = str(ui.axis_selected or "").strip()
        if ui.axis_selection_changed:
            self.state.last_ui_axis_selected = ui_axis
        elif self.state.last_ui_axis_selected:
            ui_axis = self.state.last_ui_axis_selected

        fixed_axis = str(inputs.fixed_axis or "").strip()
        prev_selected = str(self.state.selected_axis or "").strip()
        fixed_applied = bool(self.state.fixed_axis_applied)

        items = [NOT_ATTACHED] + axis_ids
        combo_enabled = True
        combo_current = NOT_ATTACHED
        if fixed_axis and fixed_axis in axis_ids:
            selected_axis = fixed_axis
            combo_current = fixed_axis
            fixed_applied = True
            combo_enabled = not (bool(inputs.lock_axis_combo) and fixed_applied)
        else:
            if ui_axis in axis_ids:
                selected_axis = ui_axis
            elif ui_axis == NOT_ATTACHED or not ui_axis:
                selected_axis = ""
            else:
                selected_axis = ""

            if ui_axis in items:
                combo_current = ui_axis
            elif prev_selected in axis_ids:
                combo_current = prev_selected
            else:
                combo_current = NOT_ATTACHED

        attach_combo = HipAttachCombo(
            items=items,
            current=combo_current,
            enabled=bool(combo_enabled),
            fixed_axis_applied=bool(fixed_applied),
        )

        intents: list[object] = []
        if ui.axis_selection_changed:
            if prev_selected and (not selected_axis or prev_selected != selected_axis):
                intents.append(ReleaseAxis(axis_id=prev_selected, hip_id=hip_id))
            if selected_axis and selected_axis != prev_selected:
                intents.append(ClaimAxis(axis_id=selected_axis, hip_id=hip_id))

        axis_id = str(selected_axis or fixed_axis or "").strip()
        attached = bool(selected_axis or fixed_axis)
        mode_now = str(getattr(snap, "mode", "") or "")

        if axis_id and self.state.joy.deadman and str(mode_now).upper() == "LIVE":
            owner = self._get_claim_owner(snap, axis_id)
            if owner == str(hip_id or ""):
                intent = map_soll_speed_to_jog_winch(
                    winch_id=axis_id,
                    soll_speed=float(self.state.joy.soll_speed),
                    hip_id=hip_id,
                )
                if intent is not None and self._should_emit_speed(axis_id, float(intent.rate)):
                    intents.append(intent)

        if self.state.joy.select_hip and axis_id:
            owner = self._get_claim_owner(snap, axis_id)
            if owner != str(hip_id or ""):
                has_claim = any(
                    isinstance(i, ClaimAxis) and str(getattr(i, "axis_id", "")) == axis_id
                    for i in intents
                )
                if (not has_claim) and self._claim_allowed(axis_id, int(inputs.now_ns)):
                    intents.append(ClaimAxis(axis_id=axis_id, hip_id=hip_id))

        prev_device_tick = self.state.prev_device_tick
        tick_text, new_prev = self._compute_tick_text(
            snap=snap,
            axis_id=axis_id,
            prev_device_tick=prev_device_tick,
        )

        lifetick_age = self._get_lifetick_age(snap=snap, axis_id=axis_id)
        online_state = None
        if lifetick_age is not None:
            online_state = age_to_online_state(age=float(lifetick_age), good_max=30.0, warn_max=500.0)

        age_ms: int | None
        if inputs.last_rx_ns is None:
            age_ms = None
        else:
            age_ms = int((int(inputs.now_ns) - int(inputs.last_rx_ns)) / 1_000_000.0)
        stale = (age_ms is None) or (age_ms >= int(inputs.stale_after_ms))

        estop = bool(getattr(snap, "estop", False))
        fault = bool(getattr(snap, "fault", False))

        main_text, slave_text = self._compute_drive_status_texts(snap=snap, axis_id=axis_id)
        drive_status_summary = f"{main_text}|{slave_text}" if (main_text or slave_text) else ""
        drive_status = HipDriveStatusState(main_text=str(main_text), slave_text=str(slave_text))

        now_s = float(inputs.now_ns) / 1e9
        estop_word = int(self._parse_estop_word_from_snapshot(snap))
        logical = decode_estop_word(estop_word)

        axis_id_for_estate = axis_id
        if not axis_id_for_estate:
            if axis_ids:
                axis_id_for_estate = axis_ids[0]
            else:
                axis_id_for_estate = "X"

        taster = bool(logical.get("taster", False))
        self._update_taster_edge(axis_id_for_estate, taster, now_s)
        within_banner = self._within_brake_grace(axis_id_for_estate, now_s, 2.0)
        within_brake = self._within_brake_grace(axis_id_for_estate, now_s, 3.0)

        estate = derive_banner_estate_from_word(
            int(estop_word),
            within_brake_grace=(lambda: bool(within_banner)),
        )

        def _brake_ok_display(raw: bool) -> bool:
            if bool(taster) and bool(within_brake):
                return True
            return bool(raw)

        profile = infer_estop_profile(logical)

        joy = getattr(snap, "joy", None) or JoyState()
        joy_deadman = bool(getattr(joy, "deadman", False))
        joy_select_hip = bool(getattr(joy, "select_hip", False))
        joy_soll_speed = float(getattr(joy, "soll_speed", 0.0) or 0.0)

        readouts = None
        cut_markers = None
        params = getattr(snap, "params", {}) or {}
        if attached and axis_id and axis_id in axes:
            ax = axes.get(axis_id)
            pos, vel = self._read_axis_pos_vel(ax)
            amp, tmp = self._read_amp_and_temp(params=params, snap=snap)
            readouts = self._compute_readouts_state(
                ax=ax,
                pos=pos,
                vel=vel,
                amp=amp,
                temp=tmp,
                params=params,
                snap=snap,
            )
            cut_markers = self._compute_cut_markers_state(
                snap=snap,
                params=params,
                estate=estate,
            )

        param_writeback_group = ""
        param_writeback_values: dict[str, float] = {}
        param_writeback_message = ""

        # --- UI actions -> intents (param ops, estop reset, resync) ---
        if ui.estop_reset_clicked and axis_id:
            intents.append(RequestEstopReset(axis_id=axis_id, hip_id=hip_id))

        resync_ignored = False
        resync_reason = ""
        if ui.resync_clicked:
            if (str(mode_now).upper() != "IDLE") or (str(estate).upper() != "IDLE"):
                resync_ignored = True
                resync_reason = f"mode={str(mode_now)} estate={str(estate)}"
            else:
                intents.append(RequestResync(axis_id=str(axis_id or ""), hip_id=hip_id))
                if readouts is not None:
                    cut_markers = HipCutMarkersState("--", "--", "--", "--")

        # Apply core acks before param txn decisions
        self._param_txn.handle_core_acks(list(inputs.core_acks or []))

        for action in list(ui.param_actions or []):
            if not axis_id:
                continue
            group = str(action.group or "")
            kind = str(action.kind or "")
            if kind == "edit":
                self._param_txn.start_local_edit(group)
                intent = self._param_txn.make_begin_intent(axis_id=axis_id, group=group)
                self._param_txn.send(intent, group=group, kind="begin", publish=intents.append, now_ns=int(inputs.now_ns))
            elif kind == "write":
                vals = dict(ui.param_values.get(group, {}) if isinstance(ui.param_values, dict) else {})
                fixed = dict(vals)
                if group == "pos":
                    fixed = self._normalize_pos_chain(fixed)
                elif group == "guider":
                    fixed = self._normalize_guider_range(fixed)

                if fixed != vals:
                    param_writeback_group = group
                    param_writeback_values = dict(fixed)
                    if group == "pos":
                        lines = []
                        for k in ("HardMax", "UserMax", "UserMin", "HardMin"):
                            if k in vals and k in fixed and float(vals[k]) != float(fixed[k]):
                                lines.append(f"{k}: {float(vals[k]):g} → {float(fixed[k]):g}")
                        if lines:
                            param_writeback_message = (
                                "The rule HardMax ≥ UserMax ≥ UserMin ≥ HardMin was enforced.\n\n"
                                + "\n".join(lines)
                            )

                intent = self._param_txn.make_write_intent(axis_id=axis_id, group=group, values=fixed)
                self._param_txn.send(intent, group=group, kind="write", publish=intents.append, now_ns=int(inputs.now_ns))
                self._param_txn.end_local_edit(now_ns=int(inputs.now_ns))

                self.state.pending_commit_req_id = str(getattr(intent, "req_id", "") or "")
                self.state.pending_commit_group = str(getattr(intent, "group", "") or "")
                self.state.pending_commit_values = dict(getattr(intent, "values", {}) or {})
            elif kind == "cancel":
                intent = self._param_txn.make_cancel_intent(axis_id=axis_id, group=group)
                self._param_txn.send(intent, group=group, kind="cancel", publish=intents.append, now_ns=int(inputs.now_ns))
                self._param_txn.end_local_edit(now_ns=int(inputs.now_ns))

        txn_events = self._param_txn.retry_pending(int(inputs.now_ns), publish=intents.append)

        # Compute param UI state
        now_ns = int(inputs.now_ns)
        edit_active, edit_group = self._param_txn.effective_remote_edit_state(
            remote_active=bool(getattr(snap, "param_edit_active", False)),
            remote_group=str(getattr(snap, "param_edit_group", "") or ""),
            now_ns=now_ns,
        )
        param_ui = self._compute_param_ui_state(
            edit_active=bool(edit_active),
            edit_group=str(edit_group or ""),
            estate=str(estate or ""),
        )

        attach_state = self.compute_attach_state(
            HipAttachInputs(
                attached=bool(attached),
                modal_locked=bool(param_ui.modal_lock_active),
                last_mode=str(mode_now or ""),
                last_estate=str(estate or ""),
            )
        )

        limit_values: dict[str, float] = {}
        try:
            for k in ("HardMin", "UserMin", "UserMax", "HardMax"):
                if k in params:
                    limit_values[k] = float(params[k])
        except Exception:
            limit_values = {}

        param_freeze_group = self._param_txn.local_edit_group if self._param_txn.local_edit_active else ""

        lifetick_intents, echo_map = self._compute_lifetick_echo_intents(
            snap=snap,
            hip_id=hip_id,
            last_lifetick_echo_sent=dict(self.state.last_lifetick_echo_sent or {}),
        )
        intents.extend(lifetick_intents)

        intents = self._gate_motion_intents(intents, deadman=self.state.joy.deadman)

        param_commit_dialog = self._maybe_build_param_commit_dialog(snap)

        presentation = HipPresentationData(
            tick_text=str(tick_text),
            age_ms=age_ms,
            stale=bool(stale),
            lifetick_age=lifetick_age,
            online_state=online_state,
            estop=bool(estop),
            fault=bool(fault),
            drive_status_summary=str(drive_status_summary or ""),
            drive_status=drive_status,
            estop_word=int(estop_word),
            within_banner=bool(within_banner),
            within_brake=bool(within_brake),
            logical=dict(logical),
            taster=bool(taster),
            attached=bool(attached),
            prev_estop_profile=str(self.state.prev_estop_profile or ""),
            joy_deadman=bool(joy_deadman),
            joy_select_hip=bool(joy_select_hip),
            joy_soll_speed=float(joy_soll_speed),
            readouts=readouts,
            cut_markers=cut_markers,
            attach_state=attach_state,
            attach_combo=attach_combo,
            param_ui=param_ui,
            param_values=dict(params or {}),
            param_freeze_group=str(param_freeze_group or ""),
            limit_values=dict(limit_values or {}),
            param_writeback_group=str(param_writeback_group or ""),
            param_writeback_values=dict(param_writeback_values or {}),
            param_writeback_message=str(param_writeback_message or ""),
            param_commit_dialog=param_commit_dialog,
        )

        self.state.prev_device_tick = new_prev
        self.state.last_lifetick_echo_sent = dict(echo_map or {})
        self.state.selected_axis = str(selected_axis or "")
        self.state.fixed_axis_applied = bool(fixed_applied)
        self.state.prev_estop_profile = str(profile or "")

        return HipStepResult(
            view_model=None,
            legacy_view_model=None,
            presentation=presentation,
            intents=intents,
            resync_ignored=bool(resync_ignored),
            resync_block_reason=str(resync_reason or ""),
            txn_events=list(txn_events or []),
        )

    def _maybe_build_param_commit_dialog(self, snap: TelemetrySnapshot) -> HipParamCommitDialog | None:
        rid = str(getattr(snap, "param_commit_req_id", "") or "")
        status = str(getattr(snap, "param_commit_status", "idle") or "idle")
        group = str(getattr(snap, "param_commit_group", "") or "")

        if not rid or rid != str(self.state.pending_commit_req_id or ""):
            return None
        if rid in self.state.commit_dialog_shown_for:
            return None
        if status not in ("applied", "timeout"):
            return None

        self.state.commit_dialog_shown_for.add(rid)

        if status == "applied":
            msg = f"{group} parameters were applied (observed in telemetry)."
            dialog = HipParamCommitDialog(level="info", title="Parameters applied", message=msg)
        else:
            unmatched = list(getattr(snap, "param_commit_unmatched", []) or [])
            params = dict(getattr(snap, "params", {}) or {})
            want = dict(self.state.pending_commit_values or {})

            lines = [
                f"{group} parameters were not confirmed (timeout).",
                "",
                "Mismatches:",
            ]
            for k in unmatched:
                w = want.get(k, "?")
                g = params.get(k, "<missing>")
                lines.append(f"- {k}: want {w}  got {g}")
            dialog = HipParamCommitDialog(level="warning", title="Parameters not confirmed", message="\n".join(lines))

        self.state.pending_commit_req_id = ""
        self.state.pending_commit_group = ""
        self.state.pending_commit_values = {}
        return dialog

    @staticmethod
    def normalize_intents(intents: Iterable[object]) -> list[tuple[str, tuple[tuple[str, Any], ...]]]:
        items: list[tuple[str, tuple[tuple[str, Any], ...]]] = []
        for intent in intents:
            name = type(intent).__name__
            raw = {}
            try:
                raw = dict(vars(intent))
            except Exception:
                raw = {}
            norm = {k: _normalize_value(v) for k, v in raw.items() if not str(k).startswith("_")}
            items.append((name, tuple(sorted(norm.items()))))
        items.sort(key=lambda x: (x[0], x[1]))
        return items

    @staticmethod
    def normalize_view_model(vm: HipViewModel) -> dict[str, Any]:
        try:
            data = asdict(vm)
        except Exception:
            data = dict(vars(vm))
        norm = _normalize_value(data)
        try:
            if "age_ms" in norm:
                norm["age_ms"] = None if norm["age_ms"] is None else int(norm["age_ms"])
            if "lifetick_age" in norm:
                norm["lifetick_age"] = None if norm["lifetick_age"] is None else int(norm["lifetick_age"])
        except Exception:
            pass
        return norm

    @staticmethod
    def _compute_tick_text(
        *,
        snap: TelemetrySnapshot,
        axis_id: str,
        prev_device_tick: int | None,
    ) -> tuple[str, int | None]:
        if not axis_id:
            return "--", None

        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return "--", None

        ax = axes.get(axis_id)
        if ax is None:
            return "--", None

        cur_raw = getattr(ax, "device_tick", 0)
        try:
            cur = int(cur_raw)
        except Exception:
            return "--", None

        delta, new_prev = compute_time_tick(prev_device_tick, cur)
        return str(int(delta)), int(new_prev)

    @staticmethod
    def _parse_estop_word_from_snapshot(snap: TelemetrySnapshot) -> int:
        fields = getattr(snap, "plc_uplink_fields", None)
        if isinstance(fields, dict):
            v = fields.get("EStopStatus")
            if v is not None:
                try:
                    return int(str(v).strip())
                except Exception:
                    pass
        return int(getattr(snap, "estop_status_word", 0) or 0)

    @staticmethod
    def _raw_uplink_float(snap: TelemetrySnapshot, key: str, default: float) -> float:
        try:
            raw = getattr(snap, "plc_uplink_fields", None)
            if isinstance(raw, dict) and key in raw:
                return float(raw.get(key, default) or default)
        except Exception:
            pass
        return float(default)

    @staticmethod
    def _raw_tail_token(snap: TelemetrySnapshot, key: str) -> str:
        try:
            tail = getattr(snap, "plc_uplink_tail", {}) or {}
            if isinstance(tail, dict):
                v = tail.get(key, "") or ""
                return str(v)
        except Exception:
            pass
        return ""

    @staticmethod
    def _read_axis_pos_vel(ax) -> tuple[float, float]:
        try:
            pos = float(getattr(ax, "pos", 0.0) or 0.0)
        except Exception:
            pos = 0.0
        try:
            vel = float(getattr(ax, "vel", 0.0) or 0.0)
        except Exception:
            vel = 0.0
        return pos, vel

    @classmethod
    def _read_amp_and_temp(cls, *, params: dict, snap: TelemetrySnapshot) -> tuple[float, float]:
        def _pf(key: str, default: float) -> float:
            try:
                return float(params.get(key, default))
            except Exception:
                return float(default)

        amp = _pf("ActCur", _pf("Amp", 0.0))
        tmp = _pf("Temp", 20.0)

        if "ActCur" not in params:
            amp = cls._raw_uplink_float(snap, "ActCurUI", amp)
        if "Temp" not in params:
            tmp = cls._raw_uplink_float(snap, "CabTemperatureUI", tmp)
        return amp, tmp

    @classmethod
    def _compute_readouts_state(
        cls,
        *,
        ax,
        pos: float,
        vel: float,
        amp: float,
        temp: float,
        params: dict,
        snap: TelemetrySnapshot,
    ) -> HipReadoutsState:
        pos_text = fmt_f_unit(pos, "m", ndigits=2)
        vel_text = f"{vel:.2f} m/s"
        amp_text = fmt_i_unit(int(round(amp)), "A")
        temp_text = f"{int(round(temp))}°"

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

        try:
            g_pos = float(params.get("GuidePosIst", 0.0) or 0.0)
        except Exception:
            g_pos = 0.0
        if g_pos == 0.0:
            g_pos = cls._raw_uplink_float(snap, "GuidePosIstUI", g_pos)

        guider_min_text = f"{g_pos_min:.3f} m"
        guider_max_text = f"{g_pos_max:.3f} m"
        guider_val_text = f"{g_pos:.3f} m"

        try:
            vel_max = float(params.get("VelMax", 0.0) or 0.0)
        except Exception:
            vel_max = 0.0
        if vel_max <= 0.0:
            vel_max = 1.0

        try:
            vel_cmd = float(getattr(ax, "vel_cmd", vel) if ax is not None else vel)
        except Exception:
            vel_cmd = vel
        scale = 1000.0
        vel_cmd_min = int(round(-vel_max * scale))
        vel_cmd_max = int(round(+vel_max * scale))
        vel_cmd_val = int(round(vel_cmd * scale))

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
        limit_min = int(round(user_min * scale))
        limit_max = int(round(user_max * scale))
        limit_val = int(round(pos * scale))

        drum_diam = 0.5
        try:
            pitch = float(params.get("Pitch", 0.0) or 0.0)
        except Exception:
            pitch = 0.0
        denom = 3.141592653589793 * drum_diam
        ratio = (pitch / denom) if (denom > 0.0 and pitch > 0.0) else 0.0

        try:
            g_vel_meas = float(params.get("GuideIstSpeed", 0.0) or 0.0)
        except Exception:
            g_vel_meas = 0.0
        if g_vel_meas == 0.0:
            g_vel_meas = cls._raw_uplink_float(snap, "GuideIstSpeedUI", g_vel_meas)

        g_vel_max = abs(vel_max) * ratio
        if g_vel_max <= 0.0:
            g_vel_max = 1.0
        if g_vel_meas > g_vel_max:
            g_vel_meas = g_vel_max
        elif g_vel_meas < -g_vel_max:
            g_vel_meas = -g_vel_max

        guider_speed_min = int(round(-g_vel_max * scale))
        guider_speed_max = int(round(+g_vel_max * scale))
        guider_speed_val = int(round(g_vel_meas * scale))
        guider_speed_text = f"{g_vel_meas:.3f} m/s"

        return HipReadoutsState(
            pos_text=str(pos_text),
            vel_text=str(vel_text),
            amp_text=str(amp_text),
            temp_text=str(temp_text),
            guider_min_text=str(guider_min_text),
            guider_max_text=str(guider_max_text),
            guider_val_text=str(guider_val_text),
            guider_speed_text=str(guider_speed_text),
            vel_cmd_min=int(vel_cmd_min),
            vel_cmd_max=int(vel_cmd_max),
            vel_cmd_val=int(vel_cmd_val),
            limit_min=int(limit_min),
            limit_max=int(limit_max),
            limit_val=int(limit_val),
            guider_range_min=int(round(g_pos_min * scale)),
            guider_range_max=int(round(g_pos_max * scale)),
            guider_range_val=int(round(g_pos * scale)),
            guider_speed_min=int(guider_speed_min),
            guider_speed_max=int(guider_speed_max),
            guider_speed_val=int(guider_speed_val),
        )

    @classmethod
    def _compute_cut_markers_state(
        cls,
        *,
        snap: TelemetrySnapshot,
        params: dict,
        estate: str,
    ) -> HipCutMarkersState:
        try:
            cut_pos = float(params.get("CutPos", 0.0) or 0.0)
            cut_vel = float(params.get("CutVel", 0.0) or 0.0)
            posdiff = float(params.get("PosDiffFor", 0.0) or 0.0)
        except Exception:
            cut_pos = 0.0
            cut_vel = 0.0
            posdiff = 0.0

        in_estop = bool(getattr(snap, "estop", False))
        try:
            word = cls._parse_estop_word_from_snapshot(snap)
            bits = decode_estop_word(int(word))
            in_estop = any(bool(bits.get(k, False)) for k in ("master", "slave", "network", "estop1", "estop2"))
        except Exception:
            pass
        if not in_estop and str(estate or "").upper() == "ESTOP":
            in_estop = True

        if not in_estop:
            cut_pos_text = "--"
            cut_vel_text = "--"
            posdiff_text = "--"
        else:
            cut_pos_text = fmt_f_unit(cut_pos, "m", ndigits=2)
            cut_vel_text = fmt_f_unit(cut_vel, "m/s", ndigits=2)
            posdiff_text = fmt_f_unit(posdiff, "m", ndigits=2)

        t_tok = cls._raw_tail_token(snap, "SystemTime")
        cut_time_text = t_tok if t_tok else "--"
        return HipCutMarkersState(
            cut_time_text=str(cut_time_text),
            cut_pos_text=str(cut_pos_text),
            cut_vel_text=str(cut_vel_text),
            posdiff_text=str(posdiff_text),
        )

    @staticmethod
    def _normalize_pos_chain(values: dict[str, float]) -> dict[str, float]:
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

    @staticmethod
    def _normalize_guider_range(values: dict[str, float]) -> dict[str, float]:
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

    @staticmethod
    def _compute_drive_status_texts(
        *,
        snap: TelemetrySnapshot,
        axis_id: str,
    ) -> tuple[str, str]:
        if decode_drive_status is None:
            return "", ""
        if not axis_id:
            return "", ""
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return "", ""
        ax = axes.get(axis_id)
        if ax is None:
            return "", ""
        main_word = int(getattr(ax, "status_word", 0) or 0)
        slave_word = int(getattr(ax, "guide_status_word", 0) or 0)
        try:
            main = decode_drive_status(main_word)
            slave = decode_drive_status(slave_word)
            return str(main.summary()), str(slave.summary())
        except Exception:
            return "", ""

    def _compute_param_ui_state(self, *, edit_active: bool, edit_group: str, estate: str) -> HipParamUiState:
        groups = ("pos", "vel", "filter", "guider")
        state_groups: dict[str, HipParamGroup] = {}
        estate = str(estate or "").upper()
        edits_allowed = estate not in ("ARMED", "READY")

        if edit_active:
            for g in groups:
                if g == edit_group:
                    busy = self._param_txn.is_group_busy(g)
                    buttons = HipParamButtons(
                        edit_enabled=False if edits_allowed else False,
                        write_enabled=bool((not busy) and edits_allowed),
                        cancel_enabled=bool(not busy),
                    )
                    if busy:
                        buttons = HipParamButtons(edit_enabled=False, write_enabled=False, cancel_enabled=False)
                    state_groups[g] = HipParamGroup(fields_enabled=bool(not busy), buttons=buttons)
                else:
                    state_groups[g] = HipParamGroup(
                        fields_enabled=False,
                        buttons=HipParamButtons(edit_enabled=False, write_enabled=False, cancel_enabled=False),
                    )
            return HipParamUiState(
                modal_lock_active=True,
                modal_lock_group=str(edit_group or ""),
                groups=state_groups,
            )

        for g in groups:
            busy = self._param_txn.is_group_busy(g)
            if busy:
                buttons = HipParamButtons(edit_enabled=False, write_enabled=False, cancel_enabled=False)
            else:
                buttons = HipParamButtons(
                    edit_enabled=bool(edits_allowed),
                    write_enabled=False,
                    cancel_enabled=False,
                )
            state_groups[g] = HipParamGroup(fields_enabled=False, buttons=buttons)

        return HipParamUiState(
            modal_lock_active=False,
            modal_lock_group="",
            groups=state_groups,
        )

    @staticmethod
    def _get_lifetick_age(*, snap: TelemetrySnapshot, axis_id: str) -> int | None:
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return None
        ax = axes.get(axis_id)
        if ax is None:
            return None
        try:
            return int(getattr(ax, "lifetick_age", 0) or 0)
        except Exception:
            return None

    @staticmethod
    def _compute_drive_status_summary(*, snap: TelemetrySnapshot, axis_id: str) -> str:
        if decode_drive_status is None:
            return ""
        if not axis_id:
            return ""
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return ""
        ax = axes.get(axis_id)
        if ax is None:
            return ""
        main_word = int(getattr(ax, "status_word", 0) or 0)
        slave_word = int(getattr(ax, "guide_status_word", 0) or 0)
        try:
            main = decode_drive_status(main_word)
            slave = decode_drive_status(slave_word)
            return f"{main.summary()}|{slave.summary()}"
        except Exception:
            return ""

    @staticmethod
    def _compute_lifetick_echo_intents(
        *,
        snap: TelemetrySnapshot,
        hip_id: str,
        last_lifetick_echo_sent: dict[str, int],
    ) -> tuple[list[object], dict[str, int]]:
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict) or not axes:
            return [], last_lifetick_echo_sent

        intents: list[object] = []
        for axis_id, ax in axes.items():
            try:
                v = int(getattr(ax, "device_tick", 0)) & 0xFFFF
            except Exception:
                v = 0

            prev = last_lifetick_echo_sent.get(axis_id)
            if prev is not None and int(prev) == v:
                continue

            last_lifetick_echo_sent[axis_id] = v
            intents.append(EchoLifeTick(axis_id=axis_id, value=v, hip_id=str(hip_id or "")))

        return intents, last_lifetick_echo_sent


def _normalize_value(val: Any) -> Any:
    if isinstance(val, float):
        return round(val, 6)
    if isinstance(val, (int, str, bool)) or val is None:
        return val
    if isinstance(val, dict):
        return {str(k): _normalize_value(v) for k, v in sorted(val.items(), key=lambda x: str(x[0]))}
    if isinstance(val, set):
        return [_normalize_value(v) for v in sorted(val, key=lambda x: str(x))]
    if isinstance(val, (list, tuple)):
        return [_normalize_value(v) for v in val]
    try:
        return str(val)
    except Exception:
        return "<unrepr>"
