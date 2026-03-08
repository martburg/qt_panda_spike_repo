from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from steuerung3d.core.telemetry_axis_view import axis_scoped_snapshot
from steuerung3d.protocol.estop_bits import decode_estop_word

from ...domain.ui_estop import age_to_online_state, infer_estop_profile
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
from .types import HipAttachInputs, HipPresentationData
from .viewmodel import HipDriveStatusState


@dataclass(frozen=True)
class HipPresentationPhase:
    presentation: HipPresentationData
    snap_view: object
    params: dict[str, Any]
    logical: dict[str, Any]
    estop_word: int
    estate: str
    estop: bool
    fault: bool
    taster: bool
    within_banner: bool
    within_brake: bool
    mode_now: str
    profile: str


def compute_presentation_phase(
    *,
    engine: object,
    attach_combo: object,
    attached: bool,
    axis_id: str,
    axis_ids: list[str],
    snap: object,
    now_ns: int,
    last_rx_ns: int | None,
    stale_after_ms: int,
    param_result: object | None = None,
    update_state: bool = True,
) -> HipPresentationPhase:
    axes = getattr(snap, "axes", {}) or {}
    mode_now = str(getattr(snap, "core_mode", "") or "")
    presentation_axis_id = axis_id if attached else ""
    snap_view = axis_scoped_snapshot(snap, presentation_axis_id)
    params = getattr(snap_view, "params", {}) or {}

    estop_word = int(parse_estop_word_from_snapshot(snap_view))
    logical = decode_estop_word(estop_word)

    axis_id_for_estate = axis_id or (axis_ids[0] if axis_ids else "X")
    taster = bool(logical.get("taster", False))
    now_s = float(now_ns) / 1e9
    if update_state:
        engine._update_taster_edge(axis_id_for_estate, taster, now_s)
    within_banner = engine._within_brake_grace(axis_id_for_estate, now_s, 2.0)
    within_brake = engine._within_brake_grace(axis_id_for_estate, now_s, 3.0)
    estate = compute_banner_estate(
        estop_word=int(estop_word),
        within_brake_grace=bool(within_banner),
    )
    profile = infer_estop_profile(logical)

    estop = bool(getattr(snap, "estop", False))
    fault = bool(getattr(snap, "fault", False))

    state = engine.state
    prev_device_tick = getattr(state, "prev_device_tick", None)
    tick_text, new_prev = compute_tick_text(
        snap=snap_view,
        axis_id=axis_id,
        prev_device_tick=prev_device_tick,
    )

    lifetick_age = get_lifetick_age(snap=snap, axis_id=axis_id)
    online_state = None
    if lifetick_age is not None:
        online_state = age_to_online_state(age=float(lifetick_age), good_max=30.0, warn_max=500.0)

    if last_rx_ns is None:
        age_ms = None
    else:
        age_ms = int((int(now_ns) - int(last_rx_ns)) / 1_000_000.0)
    stale = (age_ms is None) or (age_ms >= int(stale_after_ms))

    main_text, slave_text = compute_drive_status_texts(snap=snap, axis_id=axis_id)
    drive_status_summary = f"{main_text}|{slave_text}" if (main_text or slave_text) else ""
    drive_status = HipDriveStatusState(main_text=str(main_text), slave_text=str(slave_text))

    readouts = None
    cut_markers = None
    if attached and axis_id and axis_id in axes:
        ax = axes.get(axis_id)
        if ax is None:
            pos = 0.0
            vel = 0.0
        else:
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

    param_ui = getattr(param_result, "param_ui", None)
    attach_state = engine.compute_attach_state(
        HipAttachInputs(
            attached=bool(attached),
            modal_locked=bool(getattr(param_ui, "modal_lock_active", False)),
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
        prev_estop_profile=str(getattr(state, "prev_estop_profile", "") or ""),
        joy_deadman=False,
        joy_select_hip=False,
        joy_soll_speed=0.0,
        readouts=readouts,
        cut_markers=cut_markers,
        attach_state=attach_state,
        attach_combo=attach_combo,
        param_ui=param_ui,
        param_values=dict(params or {}),
        param_freeze_group=str(getattr(param_result, "param_freeze_group", "") or ""),
        limit_values=dict(limit_values or {}),
        param_writeback_group=str(getattr(param_result, "param_writeback_group", "") or ""),
        param_writeback_values=dict(getattr(param_result, "param_writeback_values", {}) or {}),
        param_writeback_message=str(getattr(param_result, "param_writeback_message", "") or ""),
        param_commit_dialog=getattr(param_result, "param_commit_dialog", None),
    )

    if update_state:
        state.prev_device_tick = new_prev

    return HipPresentationPhase(
        presentation=presentation,
        snap_view=snap_view,
        params=dict(params or {}),
        logical=dict(logical),
        estop_word=int(estop_word),
        estate=str(estate or ""),
        estop=bool(estop),
        fault=bool(fault),
        taster=bool(taster),
        within_banner=bool(within_banner),
        within_brake=bool(within_brake),
        mode_now=str(mode_now or ""),
        profile=str(profile or ""),
    )
