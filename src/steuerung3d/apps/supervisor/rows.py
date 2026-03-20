from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

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


@dataclass(frozen=True)
class _AxisRowDiagnostics:
    load_pct: float
    temp_c: float
    pos_diff_m: float
    system_time_token: str


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
    facts = _build_axis_row_facts(
        snap=snap,
        scoped=scoped,
        axis_id=axis.axis_id,
        densi=densi,
        ax=ax,
        stale_after_ms=stale_after_ms,
    )
    metrics = _build_axis_row_metrics(ax=ax)
    pos_user_min, pos_user_max = _build_axis_row_position_limits(scoped=scoped)
    diagnostics = _build_axis_row_diagnostics(scoped=scoped)
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
        pos_user_min=pos_user_min,
        pos_user_max=pos_user_max,
        load_pct=diagnostics.load_pct,
        temp_c=diagnostics.temp_c,
        pos_diff_m=diagnostics.pos_diff_m,
        system_time_token=diagnostics.system_time_token,
        stale=facts.stale,
        hip_open_count=int(hip_open_count),
    )


def _build_axis_row_facts(
    *,
    snap: TelemetrySnapshot,
    scoped: TelemetrySnapshot,
    axis_id: str,
    densi: object,
    ax: object,
    stale_after_ms: int,
) -> _AxisRowFacts:
    axis_word_map = _mapping_str_object(getattr(snap, "axis_estop_status_word", {}) or {})
    raw_word = axis_word_map.get(axis_id)
    fields_map = _mapping_str_object(getattr(scoped, "plc_uplink_fields", None))
    if fields_map.get("EStopStatus") is not None:
        raw_word = fields_map.get("EStopStatus")
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


def _coerce_float_like(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return float(stripped)
        except ValueError:
            return default
    return default


def _mapping_str_object(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    typed_value = cast(Mapping[object, object], value)
    out: dict[str, object] = {}
    for key, item in typed_value.items():
        if isinstance(key, str):
            out[key] = item
    return out


def _build_axis_row_position_limits(*, scoped: TelemetrySnapshot) -> tuple[float, float]:
    params = _mapping_str_object(getattr(scoped, "params", {}) or {})
    raw_min = params.get("UserMin", params.get("PosMinUserUI", 0.0))
    raw_max = params.get("UserMax", params.get("PosMaxUserUI", 0.0))

    user_min = _coerce_float_like(raw_min, 0.0)
    user_max = _coerce_float_like(raw_max, 0.0)
    if user_max < user_min:
        user_min, user_max = user_max, user_min
    return user_min, user_max


def _build_axis_row_diagnostics(*, scoped: TelemetrySnapshot) -> _AxisRowDiagnostics:
    params = _mapping_str_object(getattr(scoped, "params", {}) or {})

    fields = _mapping_str_object(getattr(scoped, "plc_uplink_fields", {}) or {})

    tail = _mapping_str_object(getattr(scoped, "plc_uplink_tail", {}) or {})

    def _as_float(*values: object, default: float = 0.0) -> float:
        for value in values:
            if value is None:
                continue
            coerced = _coerce_float_like(value, default)
            if value is not None and (
                isinstance(value, (bool, int, float))
                or (isinstance(value, str) and value.strip() != "")
            ):
                return coerced
        return float(default)

    return _AxisRowDiagnostics(
        load_pct=_as_float(params.get("MotAuslast"), fields.get("MotAuslastUI"), default=0.0),
        temp_c=_as_float(params.get("Temp"), fields.get("CabTemperatureUI"), default=0.0),
        pos_diff_m=_as_float(params.get("PosDiffFor"), fields.get("PosDiffForUI"), default=0.0),
        system_time_token=str(tail.get("SystemTime") or ""),
    )
