from __future__ import annotations

from steuerung3d.apps.yellow.engines.hip.presentation_extract import (
    parse_estop_word_from_snapshot,
)
from steuerung3d.core.telemetry import JoyState, TelemetrySnapshot
from steuerung3d.core.telemetry_axis_view import axis_scoped_snapshot
from steuerung3d.protocol.banner_estate import BANNER_DYNAMIC_EXCLUDE
from steuerung3d.protocol.estop_bits import ESTOP_CAUSE_KEYS, ESTOP_OK_KEYS, decode_estop_word

from .models import AxisConfig, AxisPhase, AxisRow


def build_axis_row(
    *,
    axis: AxisConfig,
    snap: TelemetrySnapshot,
    selected: bool,
    stale_after_ms: int,
    hip_open_count: int,
) -> AxisRow | None:
    ax = snap.axes.get(axis.axis_id)
    densi = snap.densis.get(axis.densi_id)
    if ax is None and densi is None:
        return None
    attached = bool(densi.online) if densi is not None else ax is not None
    if not attached:
        return None
    scoped = axis_scoped_snapshot(snap, axis.axis_id)
    estop_word = int(parse_estop_word_from_snapshot(scoped))
    estate = _estate_from_word(estop_word)
    stale = _is_stale(snap=snap, axis_id=axis.axis_id, densi=densi, stale_after_ms=stale_after_ms)
    phase = _phase_from(
        estate=estate,
        stale=stale,
        live_motion=_is_live(ax=ax, joy=getattr(snap, "joy", JoyState())),
    )
    return AxisRow(
        unit_id=axis.unit_id,
        axis_id=axis.axis_id,
        densi_id=axis.densi_id,
        hip_id=axis.hip_id,
        selected=bool(selected),
        phase=phase,
        estop=(phase == AxisPhase.ESTOP),
        livetick=int(getattr(ax, "device_tick", 0) or 0),
        livetick_diff=int(getattr(ax, "lifetick_age", 0) or 0),
        pos=float(getattr(ax, "pos", 0.0) or 0.0),
        vel=float(getattr(ax, "vel", 0.0) or 0.0),
        stale=stale,
        hip_open_count=int(hip_open_count),
    )


def _is_stale(*, snap: TelemetrySnapshot, axis_id: str, densi: object, stale_after_ms: int) -> bool:
    if densi is not None and bool(getattr(densi, "last_seen_age_ticks", 0) or 0):
        return int(getattr(densi, "last_seen_age_ticks", 0) or 0) * 50 >= int(stale_after_ms)
    ax = snap.axes.get(axis_id)
    if ax is None:
        return True
    age = int(getattr(ax, "lifetick_age", 0) or 0)
    return age >= int(stale_after_ms)


def _estate_from_word(word: int) -> str:
    w = int(word) & 0xFFFFFFFF
    if w == 0:
        return "ESTOP"
    bits = decode_estop_word(w)
    trip_cause = any(bool(bits.get(k, False)) for k in ESTOP_CAUSE_KEYS)
    ok_keys = [
        k
        for k in ESTOP_OK_KEYS
        if (k not in BANNER_DYNAMIC_EXCLUDE) and (k not in ("brk1_ok", "brk2_ok"))
    ]
    ok_chain_fault = any(not bool(bits.get(k, True)) for k in ok_keys)
    taster = bool(bits.get("taster", False))
    schuetz = bool(bits.get("schuetz", False))
    brk_ok = bool(bits.get("brk1_ok", True)) and bool(bits.get("brk2_ok", True))
    if trip_cause or ok_chain_fault or not schuetz:
        return "ESTOP"
    if not taster:
        return "IDLE"
    return "READY" if brk_ok else "ARMED"


def _phase_from(*, estate: str, stale: bool, live_motion: bool) -> AxisPhase:
    if stale:
        return AxisPhase.STALE
    if live_motion:
        return AxisPhase.LIVE
    estate_s = str(estate or "").upper()
    if estate_s == "READY":
        return AxisPhase.READY
    if estate_s == "ARMED":
        return AxisPhase.ARMED
    if estate_s == "IDLE":
        return AxisPhase.IDLE
    return AxisPhase.ESTOP


def _is_live(*, ax: object, joy: JoyState) -> bool:
    if ax is None:
        return False
    if not bool(joy.deadman):
        return False
    return abs(float(getattr(ax, "vel", 0.0) or 0.0)) > 1e-6 or abs(float(joy.soll_speed)) > 1e-6
