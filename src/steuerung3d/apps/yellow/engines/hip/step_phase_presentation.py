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


@dataclass(frozen=True)
class _EstopFacts:
    estop_word: int
    logical: dict[str, Any]
    estate: str
    profile: str
    taster: bool
    within_banner: bool
    within_brake: bool


@dataclass(frozen=True)
class _TransportFacts:
    tick_text: str
    new_prev: int | None
    lifetick_age: int | None
    online_state: str | None
    age_ms: int | None
    stale: bool


@dataclass(frozen=True)
class _DriveAndReadoutFacts:
    drive_status_summary: str
    drive_status: HipDriveStatusState
    readouts: Any
    cut_markers: Any
    limit_values: dict[str, float]


def _build_snap_context(
    *, attached: bool, axis_id: str, snap: object
) -> tuple[str, object, dict[str, Any], dict[str, Any], str]:
    axes = getattr(snap, "axes", {}) or {}
    mode_now = str(getattr(snap, "core_mode", "") or "")
    presentation_axis_id = axis_id if attached else ""
    snap_view = axis_scoped_snapshot(snap, presentation_axis_id)
    params = getattr(snap_view, "params", {}) or {}
    return mode_now, snap_view, params, axes, presentation_axis_id


def _derive_estop_facts(
    *,
    engine: object,
    axis_id_for_estate: str,
    now_ns: int,
    snap_view: object,
    update_state: bool,
) -> _EstopFacts:
    estop_word = int(parse_estop_word_from_snapshot(snap_view))
    logical = decode_estop_word(estop_word)
    taster = bool(logical.get("taster", False))
    now_s = float(now_ns) / 1e9
    if update_state:
        engine._update_taster_edge(axis_id_for_estate, taster, now_s)
    within_banner = engine._within_brake_grace(axis_id_for_estate, now_s, 2.0)
    within_brake = engine._within_brake_grace(axis_id_for_estate, now_s, 3.0)
    estate = compute_banner_estate(
        estop_word=int(estop_word), within_brake_grace=bool(within_banner)
    )
    profile = infer_estop_profile(logical)
    return _EstopFacts(
        estop_word=int(estop_word),
        logical=dict(logical),
        estate=str(estate or ""),
        profile=str(profile or ""),
        taster=bool(taster),
        within_banner=bool(within_banner),
        within_brake=bool(within_brake),
    )


def _derive_transport_facts(
    *,
    axis_id: str,
    last_rx_ns: int | None,
    now_ns: int,
    stale_after_ms: int,
    snap: object,
    snap_view: object,
    state: object,
) -> _TransportFacts:
    prev_device_tick = getattr(state, "prev_device_tick", None)
    tick_text, new_prev = compute_tick_text(
        snap=snap_view, axis_id=axis_id, prev_device_tick=prev_device_tick
    )
    lifetick_age = get_lifetick_age(snap=snap, axis_id=axis_id)
    online_state = None
    if lifetick_age is not None:
        online_state = age_to_online_state(age=float(lifetick_age), good_max=30.0, warn_max=500.0)
    age_ms = None if last_rx_ns is None else int((int(now_ns) - int(last_rx_ns)) / 1_000_000.0)
    stale = (age_ms is None) or (age_ms >= int(stale_after_ms))
    return _TransportFacts(
        tick_text=str(tick_text),
        new_prev=new_prev,
        lifetick_age=lifetick_age,
        online_state=online_state,
        age_ms=age_ms,
        stale=bool(stale),
    )


def _derive_drive_and_readout_facts(
    *,
    attached: bool,
    axis_id: str,
    axes: dict[str, Any],
    estate: str,
    mode_now: str,
    params: dict[str, Any],
    snap: object,
    snap_view: object,
) -> _DriveAndReadoutFacts:
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
            ax=ax, pos=pos, vel=vel, amp=amp, temp=tmp, params=params, snap=snap_view
        )
        cut_markers = compute_cut_markers_state(
            snap=snap_view, params=params, estate=estate, mode=str(mode_now)
        )

    limit_values: dict[str, float] = {}
    try:
        for k in ("HardMin", "UserMin", "UserMax", "HardMax"):
            if k in params:
                limit_values[k] = float(params[k])
    except Exception:
        limit_values = {}

    return _DriveAndReadoutFacts(
        drive_status_summary=str(drive_status_summary or ""),
        drive_status=drive_status,
        readouts=readouts,
        cut_markers=cut_markers,
        limit_values=limit_values,
    )


def _derive_attach_state(
    *, engine: object, attached: bool, mode_now: str, estate: str, param_result: object | None
) -> tuple[Any, Any]:
    param_ui = getattr(param_result, "param_ui", None)
    attach_state = engine.compute_attach_state(
        HipAttachInputs(
            attached=bool(attached),
            modal_locked=bool(getattr(param_ui, "modal_lock_active", False)),
            last_mode=str(mode_now or ""),
            last_estate=str(estate or ""),
        )
    )
    return attach_state, param_ui


def _build_presentation(
    *,
    attach_combo: object,
    attach_state: Any,
    attached: bool,
    drive_facts: _DriveAndReadoutFacts,
    estop: bool,
    estop_facts: _EstopFacts,
    fault: bool,
    param_result: object | None,
    param_ui: Any,
    params: dict[str, Any],
    state: object,
    transport_facts: _TransportFacts,
) -> HipPresentationData:
    return HipPresentationData(
        tick_text=str(transport_facts.tick_text),
        age_ms=transport_facts.age_ms,
        stale=bool(transport_facts.stale),
        lifetick_age=transport_facts.lifetick_age,
        online_state=transport_facts.online_state,
        estop=bool(estop),
        fault=bool(fault),
        drive_status_summary=str(drive_facts.drive_status_summary or ""),
        drive_status=drive_facts.drive_status,
        estop_word=int(estop_facts.estop_word),
        within_banner=bool(estop_facts.within_banner),
        within_brake=bool(estop_facts.within_brake),
        logical=dict(estop_facts.logical),
        taster=bool(estop_facts.taster),
        attached=bool(attached),
        prev_estop_profile=str(getattr(state, "prev_estop_profile", "") or ""),
        joy_deadman=False,
        joy_select_hip=False,
        joy_soll_speed=0.0,
        readouts=drive_facts.readouts,
        cut_markers=drive_facts.cut_markers,
        attach_state=attach_state,
        attach_combo=attach_combo,
        param_ui=param_ui,
        param_values=dict(params or {}),
        param_freeze_group=str(getattr(param_result, "param_freeze_group", "") or ""),
        limit_values=dict(drive_facts.limit_values or {}),
        param_writeback_group=str(getattr(param_result, "param_writeback_group", "") or ""),
        param_writeback_values=dict(getattr(param_result, "param_writeback_values", {}) or {}),
        param_writeback_message=str(getattr(param_result, "param_writeback_message", "") or ""),
        param_commit_dialog=getattr(param_result, "param_commit_dialog", None),
    )


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
    mode_now, snap_view, params, axes, _presentation_axis_id = _build_snap_context(
        attached=attached,
        axis_id=axis_id,
        snap=snap,
    )
    axis_id_for_estate = axis_id or (axis_ids[0] if axis_ids else "X")
    estop_facts = _derive_estop_facts(
        engine=engine,
        axis_id_for_estate=axis_id_for_estate,
        now_ns=now_ns,
        snap_view=snap_view,
        update_state=update_state,
    )

    estop = bool(getattr(snap, "estop", False))
    fault = bool(getattr(snap, "fault", False))
    state = engine.state
    transport_facts = _derive_transport_facts(
        axis_id=axis_id,
        last_rx_ns=last_rx_ns,
        now_ns=now_ns,
        stale_after_ms=stale_after_ms,
        snap=snap,
        snap_view=snap_view,
        state=state,
    )
    drive_facts = _derive_drive_and_readout_facts(
        attached=attached,
        axis_id=axis_id,
        axes=axes,
        estate=estop_facts.estate,
        mode_now=mode_now,
        params=params,
        snap=snap,
        snap_view=snap_view,
    )
    attach_state, param_ui = _derive_attach_state(
        engine=engine,
        attached=attached,
        mode_now=mode_now,
        estate=estop_facts.estate,
        param_result=param_result,
    )
    presentation = _build_presentation(
        attach_combo=attach_combo,
        attach_state=attach_state,
        attached=attached,
        drive_facts=drive_facts,
        estop=estop,
        estop_facts=estop_facts,
        fault=fault,
        param_result=param_result,
        param_ui=param_ui,
        params=params,
        state=state,
        transport_facts=transport_facts,
    )

    if update_state:
        state.prev_device_tick = transport_facts.new_prev

    return HipPresentationPhase(
        presentation=presentation,
        snap_view=snap_view,
        params=dict(params or {}),
        logical=dict(estop_facts.logical),
        estop_word=int(estop_facts.estop_word),
        estate=str(estop_facts.estate or ""),
        estop=bool(estop),
        fault=bool(fault),
        taster=bool(estop_facts.taster),
        within_banner=bool(estop_facts.within_banner),
        within_brake=bool(estop_facts.within_brake),
        mode_now=str(mode_now or ""),
        profile=str(estop_facts.profile or ""),
    )
