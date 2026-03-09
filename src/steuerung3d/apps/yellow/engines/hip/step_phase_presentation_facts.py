from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot
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
from .viewmodel import HipDriveStatusState


class _HipPresentationState(Protocol):
    prev_device_tick: int | None


class _HipPresentationEngine(Protocol):
    state: _HipPresentationState

    def _update_taster_edge(self, axis_id: str, taster: bool, now_s: float) -> None: ...
    def _within_brake_grace(self, axis_id: str, now_s: float, grace_s: float) -> bool: ...
    def compute_attach_state(self, inputs: Any) -> Any: ...


@dataclass(frozen=True)
class EstopFacts:
    estop_word: int
    logical: dict[str, Any]
    estate: str
    profile: str
    taster: bool
    within_banner: bool
    within_brake: bool


@dataclass(frozen=True)
class TransportFacts:
    tick_text: str
    new_prev: int | None
    lifetick_age: int | None
    online_state: str | None
    age_ms: int | None
    stale: bool


@dataclass(frozen=True)
class DriveAndReadoutFacts:
    drive_status_summary: str
    drive_status: HipDriveStatusState
    readouts: Any
    cut_markers: Any
    limit_values: dict[str, float]


def build_snap_context(
    *, attached: bool, axis_id: str, snap: TelemetrySnapshot
) -> tuple[str, TelemetrySnapshot, dict[str, float], dict[str, AxisTelemetry], str]:
    axes = getattr(snap, "axes", {}) or {}
    mode_now = str(getattr(snap, "core_mode", "") or "")
    presentation_axis_id = axis_id if attached else ""
    snap_view = axis_scoped_snapshot(snap, presentation_axis_id)
    params = getattr(snap_view, "params", {}) or {}
    return mode_now, snap_view, params, axes, presentation_axis_id


def derive_estop_facts(
    *,
    engine: _HipPresentationEngine,
    axis_id_for_estate: str,
    now_ns: int,
    snap_view: TelemetrySnapshot,
    update_state: bool,
) -> EstopFacts:
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
    return EstopFacts(
        estop_word=int(estop_word),
        logical=dict(logical),
        estate=str(estate or ""),
        profile=str(profile or ""),
        taster=bool(taster),
        within_banner=bool(within_banner),
        within_brake=bool(within_brake),
    )


def derive_transport_facts(
    *,
    axis_id: str,
    last_rx_ns: int | None,
    now_ns: int,
    stale_after_ms: int,
    snap: TelemetrySnapshot,
    snap_view: TelemetrySnapshot,
    state: _HipPresentationState,
) -> TransportFacts:
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
    return TransportFacts(
        tick_text=str(tick_text),
        new_prev=new_prev,
        lifetick_age=lifetick_age,
        online_state=online_state,
        age_ms=age_ms,
        stale=bool(stale),
    )


def derive_drive_and_readout_facts(
    *,
    attached: bool,
    axis_id: str,
    axes: dict[str, AxisTelemetry],
    estate: str,
    mode_now: str,
    params: dict[str, float],
    snap: TelemetrySnapshot,
    snap_view: TelemetrySnapshot,
) -> DriveAndReadoutFacts:
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
    return DriveAndReadoutFacts(
        drive_status_summary=str(drive_status_summary or ""),
        drive_status=drive_status,
        readouts=readouts,
        cut_markers=cut_markers,
        limit_values=limit_values,
    )


def derive_attach_state(
    *,
    engine: _HipPresentationEngine,
    attached: bool,
    mode_now: str,
    estate: str,
    param_result: object | None,
) -> tuple[Any, Any]:
    from .types import HipAttachInputs

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
