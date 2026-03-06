"""HiP engine step pipeline (extracted).

No semantic changes intended; this is a mechanical extraction from `engine.py`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for type checking; avoids runtime import cycles.
    from .engine import HipEngine

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.intents import (
    ClaimAxis,
    EnableAxis,
    JogWinch,
    RequestEstopReset,
    RequestGuiderReset,
    RequestMainReset,
    RequestResync,
)
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry_axis_view import axis_scoped_snapshot
from steuerung3d.protocol.estop_bits import decode_estop_word

from ...domain.joy_motion_map import map_soll_speed_to_jog_winch
from ...domain.ui_estop import age_to_online_state, infer_estop_profile
from .intent_policy import (
    claim_allowed,
    gate_motion_intents,
    get_claim_owner,
    should_emit_enable,
    should_emit_speed,
)
from .param_ui import run_param_txn
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
from .step_context import build_step_context
from .types import (
    HipAttachInputs,
    HipPresentationData,
    HipStepInputs,
    HipStepResult,
)
from .viewmodel import HipDriveStatusState

log = logging.getLogger("hi_p")


def step(*, engine: "HipEngine", inputs: HipStepInputs) -> HipStepResult:
    """Run one HiP engine tick."""
    self = engine

    ctx = build_step_context(engine=self, inputs=inputs)

    snap = ctx.snap
    ui = ctx.ui
    hip_id = ctx.hip_id
    axis_ids = ctx.axis_ids

    axes = getattr(snap, "axes", None)
    axes = axes if isinstance(axes, dict) else {}

    attach_combo = ctx.attach_combo
    selected_axis = ctx.selected_axis
    fixed_applied = ctx.fixed_applied
    intents: list[object] = list(ctx.intents)

    fixed_axis = normalize_axis_id(inputs.fixed_axis)
    axis_id = normalize_axis_id(selected_axis or fixed_axis)
    attached = bool(selected_axis) or bool(fixed_axis)
    mode_now = str(getattr(snap, "core_mode", "") or "")

    motion_axis_id = axis_id
    if not motion_axis_id and len(axis_ids) == 1:
        motion_axis_id = axis_ids[0]
    if (not motion_axis_id) and self.state.joy.deadman and self.state.joy.select_hip:
        actionable: list[str] = []
        for axis_key in axis_ids:
            ax = axes.get(axis_key)
            if ax is None:
                continue
            in_scope = getattr(ax, "in_scope", True)
            if in_scope is None:
                in_scope = True
            if not bool(in_scope):
                continue
            if bool(getattr(ax, "fault", False)):
                continue
            actionable.append(str(axis_key))
        if len(actionable) == 1:
            # Single-axis bring-up: avoid ambiguous selection mapping.
            motion_axis_id = actionable[0]

    snap_view = axis_scoped_snapshot(snap, axis_id or motion_axis_id)
    params = getattr(snap_view, "params", {}) or {}

    now_s = float(inputs.now_ns) / 1e9
    estop_word = int(parse_estop_word_from_snapshot(snap_view))
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
        snap=snap_view,
        axis_id=axis_id,
        prev_device_tick=prev_device_tick,
    )

    lifetick_age = get_lifetick_age(snap=snap_view, axis_id=axis_id)
    online_state = None
    if lifetick_age is not None:
        online_state = age_to_online_state(age=float(lifetick_age), good_max=30.0, warn_max=500.0)

    age_ms: int | None
    if inputs.last_rx_ns is None:
        age_ms = None
    else:
        age_ms = int((int(inputs.now_ns) - int(inputs.last_rx_ns)) / 1_000_000.0)
    stale = (age_ms is None) or (age_ms >= int(inputs.stale_after_ms))

    main_text, slave_text = compute_drive_status_texts(snap=snap_view, axis_id=axis_id)
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
        amp, tmp = read_amp_and_temp(params=params, snap=snap_view)
        readouts = compute_readouts_state(
            ax=ax,
            pos=pos,
            vel=vel,
            amp=amp,
            temp=tmp,
            params=params,
            snap=snap_view,
        )
        cut_markers = compute_cut_markers_state(
            snap=snap_view,
            params=params,
            estate=estate,
            mode=str(mode_now),
        )

    # --- UI actions -> intents (param ops, estop reset, resync) ---
    if ui.estop_reset_clicked and axis_id:
        intents.append(RequestEstopReset(axis_id=axis_id, hip_id=hip_id))

    if ui.main_reset_clicked and axis_id:
        intents.append(RequestMainReset(axis_id=axis_id, hip_id=hip_id))
    if ui.guider_reset_clicked and axis_id:
        intents.append(RequestGuiderReset(axis_id=axis_id, hip_id=hip_id))

    resync_ignored = False
    resync_reason = ""
    if ui.resync_clicked:
        if str(mode_now).upper() != "IDLE":
            resync_ignored = True
            resync_reason = f"mode={str(mode_now)} estate={str(estate)}"
        else:
            intents.append(RequestResync(axis_id=str(axis_id or ""), hip_id=hip_id))

    param_result = run_param_txn(
        txn=self._param_txn,
        state=self.state,
        ui=ui,
        axis_id=str(axis_id or ""),
        now_ns=int(inputs.now_ns),
        estate=str(estate or ""),
        snap=snap_view,
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
