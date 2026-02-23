"""Qt-free HiP engine (minimal seam).

Purpose: provide a stable place to compute attach-state enablement and banner
estate without changing controller behavior. This is used for shadow-mode
comparison before cutover.
"""

from __future__ import annotations

from dataclasses import asdict
import logging
from typing import Any, Iterable

from steuerung3d.core.intents import (
    ClaimAxis,
    EchoLifeTick,
    EnableAxis,
    JogWinch,
    ReleaseAxis,
    RequestEstopReset,
    RequestResync,
)
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.estop_bits import ESTOP_SPECS, decode_estop_word

from ...domain.param_txn import ParamEditTxnClient, RetryEvent
from ...domain.taster_edge_state import TasterEdgeState, update_taster_edge_state, within_brake_grace
from ...domain.ui_estop import age_to_online_state, infer_estop_profile
from ...domain.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS, LIMIT_WIDGETS as _LIMIT_WIDGETS
from ...domain.joy_motion_map import map_soll_speed_to_jog_winch
from .types import HipPresentationData
from .attach_state import NOT_ATTACHED, build_attach_combo, compute_attach_state
from .intent_policy import (
    claim_allowed,
    gate_motion_intents,
    get_claim_owner,
    is_motion_intent,
    should_emit_enable,
    should_emit_speed,
)
from .presentation import (
    compute_banner_estate,
    compute_cut_markers_state,
    compute_drive_status_texts,
    compute_readouts_state,
    compute_tick_text,
    get_lifetick_age,
    parse_estop_word_from_snapshot,
    read_amp_and_temp,
    read_axis_pos_vel,
)
from .param_ui import run_param_txn

from .types import (
    HipAttachInputs,
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
from .viewmodel import HipCutMarkersState, HipDriveStatusState, HipReadoutsState, HipViewModel

log = logging.getLogger("hi_p")

class HipEngine:
    """Minimal HipEngine surface (shadow-mode only)."""

    def __init__(self, *, hip_id: str = "") -> None:
        self._param_txn = ParamEditTxnClient(hip_id=str(hip_id or ""))
        self._taster_state: dict[str, TasterEdgeState] = {}
        self.state = HipState()

    @staticmethod
    def _is_motion_intent(intent: object) -> bool:
        return is_motion_intent(intent)

    def _gate_motion_intents(self, intents: Iterable[object], *, deadman: bool) -> list[object]:
        return gate_motion_intents(intents, deadman=deadman)

    def _update_taster_edge(self, axis_id: str, taster: bool, now_s: float) -> None:
        prev = self._taster_state.get(axis_id, TasterEdgeState())
        self._taster_state[axis_id] = update_taster_edge_state(
            state=prev,
            taster=bool(taster),
            now_s=float(now_s),
        )

    def _within_brake_grace(self, axis_id: str, now_s: float, grace_s: float) -> bool:
        state = self._taster_state.get(axis_id, TasterEdgeState())
        return within_brake_grace(state=state, now_s=float(now_s), grace_s=float(grace_s))

    def compute_attach_state(self, inputs: HipAttachInputs):
        return compute_attach_state(inputs)

    def compute_banner_estate(self, inputs: HipBannerInputs) -> str:
        return compute_banner_estate(
            estop_word=int(inputs.estop_word),
            within_brake_grace=bool(inputs.within_brake_grace),
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

        attach_combo, selected_axis, fixed_applied = build_attach_combo(
            axis_ids=list(axis_ids),
            ui_axis=str(ui_axis or ""),
            fixed_axis=str(fixed_axis or ""),
            prev_selected=str(prev_selected or ""),
            fixed_applied=bool(fixed_applied),
            lock_axis_combo=bool(inputs.lock_axis_combo),
        )

        intents: list[object] = []
        if ui.axis_selection_changed:
            if prev_selected and (not selected_axis or prev_selected != selected_axis):
                intents.append(ReleaseAxis(axis_id=prev_selected, hip_id=hip_id))
            if selected_axis and selected_axis != prev_selected:
                intents.append(ClaimAxis(axis_id=selected_axis, hip_id=hip_id))

        axis_id = str(selected_axis or fixed_axis or "").strip()
        attached = bool(selected_axis or fixed_axis)
        mode_now = str(getattr(snap, "core_mode", "") or "")

        motion_axis_id = axis_id
        if not motion_axis_id and len(axis_ids) == 1:
            motion_axis_id = axis_ids[0]

        params = getattr(snap, "params", {}) or {}

        now_s = float(inputs.now_ns) / 1e9
        estop_word = int(parse_estop_word_from_snapshot(snap))
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

        estate = compute_banner_estate(
            estop_word=int(estop_word),
            within_brake_grace=bool(within_banner),
        )

        profile = infer_estop_profile(logical)

        estop = bool(getattr(snap, "estop", False))
        fault = bool(getattr(snap, "fault", False))

        prev_jog_active = bool(self.state.joy_jog_active)
        prev_jog_axis = str(self.state.joy_jog_axis or "")

        axis_in_scope = bool(motion_axis_id and motion_axis_id in axes)
        axis = axes.get(motion_axis_id) if axis_in_scope else None
        axis_fault = bool(getattr(axis, "fault", False)) if axis is not None else False

        owner = get_claim_owner(snap, motion_axis_id) if motion_axis_id else ""
        owner_ok = owner == str(hip_id or "")

        speed = float(self.state.joy.soll_speed)
        speed_active = abs(speed) > 1e-3
        armed_ok = str(estate or "").upper() in ("ARMED", "READY")
        ready_ok = bool(logical.get("ready", False))

        jog_allowed = (
            axis_in_scope
            and (str(mode_now).upper() == "LIVE")
            and (not estop)
            and (not fault)
            and (not axis_fault)
            and bool(taster)
            and bool(armed_ok)
            and bool(ready_ok)
            and owner_ok
            and self.state.joy.deadman
            and self.state.joy.select_hip
            and speed_active
        )

        def _jog_block_reason() -> str:
            if not motion_axis_id:
                return "no_axis"
            if not axis_in_scope:
                return "axis_missing"
            if str(mode_now).upper() != "LIVE":
                return f"mode={str(mode_now)}"
            if estop:
                return "estop"
            if fault or axis_fault:
                return "fault"
            if not taster:
                return "taster"
            if not armed_ok:
                return "armed"
            if not ready_ok:
                return "ready"
            if not owner_ok:
                return f"owner={owner or '-'}"
            if not self.state.joy.deadman:
                return "deadman"
            if not self.state.joy.select_hip:
                return "select"
            if not speed_active:
                return "zero_speed"
            return "unknown"

        if prev_jog_active and prev_jog_axis and prev_jog_axis != str(motion_axis_id or ""):
            if should_emit_speed(
                self.state.last_sent_speed_by_axis,
                prev_jog_axis,
                0.0,
            ):
                intents.append(JogWinch(winch_id=prev_jog_axis, rate=0.0, hip_id=hip_id))

        jog_rate = 0.0
        stop_reason = ""
        if jog_allowed:
            try:
                vel_max_mps = float(params.get("VelMax", 0.0) or 0.0)
            except Exception:
                vel_max_mps = 0.0
            if vel_max_mps <= 0.0 and abs(float(speed)) > 0.0:
                log.debug("HiP vel_max unavailable for axis %s", motion_axis_id)

            if should_emit_enable(
                self.state.last_sent_enable_by_axis,
                motion_axis_id,
                True,
            ):
                intents.append(EnableAxis(axis_id=motion_axis_id, enable=True, hip_id=hip_id))

            intent = map_soll_speed_to_jog_winch(
                winch_id=motion_axis_id,
                soll_speed=float(speed),
                vel_max=float(vel_max_mps),
                hip_id=hip_id,
            )
            if intent is not None:
                jog_rate = float(intent.rate)
                if should_emit_speed(
                    self.state.last_sent_speed_by_axis,
                    motion_axis_id,
                    float(intent.rate),
                ):
                    intents.append(intent)
        else:
            stop_axis_id = prev_jog_axis or str(motion_axis_id or "")
            if stop_axis_id:
                if should_emit_speed(
                    self.state.last_sent_speed_by_axis,
                    stop_axis_id,
                    0.0,
                ):
                    intents.append(JogWinch(winch_id=stop_axis_id, rate=0.0, hip_id=hip_id))
                if (not self.state.joy.deadman) and should_emit_enable(
                    self.state.last_sent_enable_by_axis,
                    stop_axis_id,
                    False,
                ):
                    intents.append(EnableAxis(axis_id=stop_axis_id, enable=False, hip_id=hip_id))
            stop_reason = _jog_block_reason()

        if prev_jog_active and (not jog_allowed or prev_jog_axis != str(motion_axis_id or "")):
            axis_for_log = prev_jog_axis or str(motion_axis_id or "")
            if axis_for_log:
                reason = stop_reason if not jog_allowed else "axis_changed"
                log.info("JOY jog stopped axis=%s reason=%s", axis_for_log, reason)

        if jog_allowed and (not prev_jog_active or prev_jog_axis != str(motion_axis_id or "")):
            if motion_axis_id:
                log.info("JOY jog enabled axis=%s vel=%.3f", motion_axis_id, jog_rate)

        self.state.joy_jog_active = bool(jog_allowed)
        self.state.joy_jog_axis = str(motion_axis_id or "") if jog_allowed else ""

        if self.state.joy.select_hip and axis_id:
            owner = get_claim_owner(snap, axis_id)
            if owner != str(hip_id or ""):
                has_claim = any(
                    isinstance(i, ClaimAxis) and str(getattr(i, "axis_id", "")) == axis_id
                    for i in intents
                )
                if (not has_claim) and claim_allowed(
                    self.state.last_claim_attempt_ns_by_axis,
                    axis_id,
                    int(inputs.now_ns),
                ):
                    intents.append(ClaimAxis(axis_id=axis_id, hip_id=hip_id))

        prev_device_tick = self.state.prev_device_tick
        tick_text, new_prev = compute_tick_text(
            snap=snap,
            axis_id=axis_id,
            prev_device_tick=prev_device_tick,
        )

        lifetick_age = get_lifetick_age(snap=snap, axis_id=axis_id)
        online_state = None
        if lifetick_age is not None:
            online_state = age_to_online_state(age=float(lifetick_age), good_max=30.0, warn_max=500.0)

        age_ms: int | None
        if inputs.last_rx_ns is None:
            age_ms = None
        else:
            age_ms = int((int(inputs.now_ns) - int(inputs.last_rx_ns)) / 1_000_000.0)
        stale = (age_ms is None) or (age_ms >= int(inputs.stale_after_ms))

        main_text, slave_text = compute_drive_status_texts(snap=snap, axis_id=axis_id)
        drive_status_summary = f"{main_text}|{slave_text}" if (main_text or slave_text) else ""
        drive_status = HipDriveStatusState(main_text=str(main_text), slave_text=str(slave_text))

        def _brake_ok_display(raw: bool) -> bool:
            if bool(taster) and bool(within_brake):
                return True
            return bool(raw)

        joy = getattr(snap, "joy", None) or JoyState()
        joy_deadman = bool(getattr(joy, "deadman", False))
        joy_select_hip = bool(getattr(joy, "select_hip", False))
        joy_soll_speed = float(getattr(joy, "soll_speed", 0.0) or 0.0)

        readouts = None
        cut_markers = None
        if attached and axis_id and axis_id in axes:
            ax = axes.get(axis_id)
            pos, vel = read_axis_pos_vel(ax)
            amp, tmp = read_amp_and_temp(params=params, snap=snap)
            readouts = compute_readouts_state(
                ax=ax,
                pos=pos,
                vel=vel,
                amp=amp,
                temp=tmp,
                params=params,
                snap=snap,
            )
            cut_markers = compute_cut_markers_state(
                snap=snap,
                params=params,
                estate=estate,
            )

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

        param_result = run_param_txn(
            txn=self._param_txn,
            state=self.state,
            ui=ui,
            axis_id=str(axis_id or ""),
            now_ns=int(inputs.now_ns),
            estate=str(estate or ""),
            snap=snap,
            intents=intents,
            core_acks=list(inputs.core_acks or []),
        )
        param_ui = param_result.param_ui

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

        param_freeze_group = str(param_result.param_freeze_group or "")

        lifetick_intents, echo_map = self._compute_lifetick_echo_intents(
            snap=snap,
            hip_id=hip_id,
            last_lifetick_echo_sent=dict(self.state.last_lifetick_echo_sent or {}),
        )
        intents.extend(lifetick_intents)

        intents = gate_motion_intents(intents, deadman=self.state.joy.deadman)

        param_commit_dialog = param_result.param_commit_dialog

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
            param_writeback_group=str(param_result.param_writeback_group or ""),
            param_writeback_values=dict(param_result.param_writeback_values or {}),
            param_writeback_message=str(param_result.param_writeback_message or ""),
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
            txn_events=list(param_result.txn_events or []),
        )

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
