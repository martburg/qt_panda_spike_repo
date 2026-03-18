from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot
from steuerung3d.util.tick import compute_time_tick


def _float_from_mapping(mapping: Mapping[str, object], key: str, default: float) -> float:
    try:
        value = mapping.get(key, default)
        if value is None:
            return float(default)
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float, str)):
            return float(value)
        return float(default)
    except Exception:
        return float(default)


def compute_tick_text(
    *,
    snap: TelemetrySnapshot,
    axis_id: str,
    prev_device_tick: int | None,
) -> tuple[str, int | None]:
    if not axis_id:
        return "--", None

    ax = snap.axes.get(axis_id)
    if ax is None:
        return "--", None

    cur_raw = getattr(ax, "device_tick", 0)
    try:
        cur = int(cur_raw)
    except Exception:
        return "--", None

    delta, new_prev = compute_time_tick(prev_device_tick, cur)
    return str(int(delta)), int(new_prev)


def get_lifetick_age(*, snap: TelemetrySnapshot, axis_id: str) -> int | None:
    ax = snap.axes.get(axis_id)
    if ax is None:
        return None
    try:
        return int(getattr(ax, "lifetick_age", 0) or 0)
    except Exception:
        return None


def parse_estop_word_from_snapshot(snap: TelemetrySnapshot) -> int:
    fields = getattr(snap, "plc_uplink_fields", None)
    if isinstance(fields, Mapping):
        fields_map = cast(Mapping[str, object], fields)
        v = fields_map.get("EStopStatus")
        if v is not None:
            try:
                return int(str(v).strip())
            except Exception:
                pass
    return int(getattr(snap, "estop_status_word", 0) or 0)


def raw_uplink_float(snap: TelemetrySnapshot, key: str, default: float) -> float:
    try:
        raw = getattr(snap, "plc_uplink_fields", None)
        if isinstance(raw, Mapping) and key in raw:
            raw_map = cast(Mapping[str, object], raw)
            return _float_from_mapping(raw_map, key, default)
    except Exception:
        pass
    return float(default)


def raw_tail_token(snap: TelemetrySnapshot, key: str) -> str:
    try:
        tail = getattr(snap, "plc_uplink_tail", {}) or {}
        if isinstance(tail, Mapping):
            tail_map = cast(Mapping[str, object], tail)
            v = tail_map.get(key, "") or ""
            return str(v)
    except Exception:
        pass
    return ""


def read_axis_pos_vel(ax: AxisTelemetry) -> tuple[float, float]:
    try:
        pos = float(getattr(ax, "pos", 0.0) or 0.0)
    except Exception:
        pos = 0.0
    try:
        vel = float(getattr(ax, "vel", 0.0) or 0.0)
    except Exception:
        vel = 0.0
    return pos, vel


def read_amp_and_temp(
    *, params: Mapping[str, float], snap: TelemetrySnapshot
) -> tuple[float, float]:
    def _pf(key: str, default: float) -> float:
        try:
            return float(params.get(key, default))
        except Exception:
            return float(default)

    amp = _pf("ActCur", _pf("Amp", 0.0))
    tmp = _pf("Temp", 20.0)

    if "ActCur" not in params:
        amp = raw_uplink_float(snap, "ActCurUI", amp)
    if "Temp" not in params:
        tmp = raw_uplink_float(snap, "CabTemperatureUI", tmp)
    return amp, tmp
