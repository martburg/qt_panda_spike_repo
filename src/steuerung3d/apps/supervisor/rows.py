from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.apps.yellow.engines.hip.presentation_extract import (
    parse_estop_word_from_snapshot,
)
from steuerung3d.core.telemetry import JoyState, TelemetrySnapshot
from steuerung3d.core.telemetry_axis_view import axis_scoped_snapshot
from steuerung3d.protocol.estop_bits import decode_estop_word

from .models import AxisConfig, AxisRow
from .row_estate import estate_from_word
from .row_estop_dots import SUPERVISOR_ESTOP_COLUMNS
from .row_phase import is_live_motion, phase_from_facts
from .row_staleness import axis_is_stale


@dataclass(frozen=True)
class _AxisRowFacts:
    estate: str
    estop_word: int
    estop_dots: tuple[bool | None, ...]
    stale: bool
    live_motion: bool


@dataclass(frozen=True)
class _AxisRowMetrics:
    livetick: int
    livetick_diff: int
    pos: float
    vel: float


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

    facts = _build_axis_row_facts(
        snap=snap,
        axis_id=axis.axis_id,
        densi=densi,
        ax=ax,
        stale_after_ms=stale_after_ms,
    )
    metrics = _build_axis_row_metrics(ax=ax)
    phase = phase_from_facts(
        estate=facts.estate,
        stale=facts.stale,
        live_motion=facts.live_motion,
    )
    return AxisRow(
        unit_id=axis.unit_id,
        axis_id=axis.axis_id,
        densi_id=axis.densi_id,
        hip_id=axis.hip_id,
        selected=bool(selected),
        phase=phase,
        estop=(phase == phase.ESTOP),
        estop_word=facts.estop_word,
        estop_dots=facts.estop_dots,
        livetick=metrics.livetick,
        livetick_diff=metrics.livetick_diff,
        pos=metrics.pos,
        vel=metrics.vel,
        stale=facts.stale,
        hip_open_count=int(hip_open_count),
    )


def _build_axis_row_facts(
    *,
    snap: TelemetrySnapshot,
    axis_id: str,
    densi: object,
    ax: object,
    stale_after_ms: int,
) -> _AxisRowFacts:
    scoped = axis_scoped_snapshot(snap, axis_id)
    axis_word_map = getattr(snap, "axis_estop_status_word", {}) or {}
    raw_word = axis_word_map.get(axis_id)
    fields = getattr(scoped, "plc_uplink_fields", None)
    if isinstance(fields, dict) and fields.get("EStopStatus") is not None:
        raw_word = fields.get("EStopStatus")
    has_estop_info = raw_word is not None
    estop_word = int(parse_estop_word_from_snapshot(scoped))
    bits = decode_estop_word(estop_word)
    joy = getattr(snap, "joy", JoyState())
    return _AxisRowFacts(
        estate=estate_from_word(estop_word),
        estop_word=estop_word,
        estop_dots=tuple(
            None
            if (not has_estop_info or not column.key)
            else column.present(bool(bits.get(column.key, False)))
            for column in SUPERVISOR_ESTOP_COLUMNS
        ),
        stale=axis_is_stale(
            snap=snap,
            axis_id=axis_id,
            densi=densi,
            stale_after_ms=stale_after_ms,
        ),
        live_motion=is_live_motion(ax=ax, joy=joy),
    )


def _build_axis_row_metrics(*, ax: object) -> _AxisRowMetrics:
    return _AxisRowMetrics(
        livetick=int(getattr(ax, "device_tick", 0) or 0),
        livetick_diff=int(getattr(ax, "lifetick_age", 0) or 0),
        pos=float(getattr(ax, "pos", 0.0) or 0.0),
        vel=float(getattr(ax, "vel", 0.0) or 0.0),
    )
