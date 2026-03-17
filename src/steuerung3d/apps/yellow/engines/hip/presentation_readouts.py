from __future__ import annotations

from typing import Mapping

from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot

from ...domain.ui_format import fmt_f_unit, fmt_i_unit
from .presentation_extract import raw_uplink_float
from .viewmodel import HipReadoutsState

_SCALE = 1000.0
_DRUM_DIAMETER = 0.5
_PI = 3.141592653589793


def _float_or_default(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except Exception:
            return default
    return default


def _param_float(params: Mapping[str, float], key: str, default: float = 0.0) -> float:
    return _float_or_default(params.get(key, default), default)


def _ordered_param_pair(
    params: Mapping[str, float], min_key: str, max_key: str, default: float = 0.0
) -> tuple[float, float]:
    min_value = _param_float(params, min_key, default)
    max_value = _param_float(params, max_key, default)
    if max_value < min_value:
        return max_value, min_value
    return min_value, max_value


def _param_or_uplink(
    params: Mapping[str, float],
    key: str,
    snap: TelemetrySnapshot,
    uplink_key: str,
    *,
    default: float = 0.0,
) -> float:
    value = _param_float(params, key, default)
    if value == 0.0:
        return raw_uplink_float(snap, uplink_key, value)
    return value


def _clamp(value: float, lower: float, upper: float) -> float:
    if value > upper:
        return upper
    if value < lower:
        return lower
    return value


def _to_scaled_int(value: float, scale: float = _SCALE) -> int:
    return int(round(value * scale))


def _axis_vel_cmd(ax: AxisTelemetry | None, fallback: float) -> float:
    source = getattr(ax, "vel_cmd", fallback) if ax is not None else fallback
    return _float_or_default(source, fallback)


def compute_readouts_state(
    *,
    ax: AxisTelemetry | None,
    pos: float,
    vel: float,
    amp: float,
    temp: float,
    params: Mapping[str, float],
    snap: TelemetrySnapshot,
) -> HipReadoutsState:
    pos_text = fmt_f_unit(pos, "m", ndigits=2)
    vel_text = f"{vel:.2f} m/s"
    amp_text = fmt_i_unit(int(round(amp)), "A")
    temp_text = f"{int(round(temp))}°"

    g_pos_min, g_pos_max = _ordered_param_pair(params, "PosMin", "PosMax")
    g_pos = _param_or_uplink(params, "GuidePosIst", snap, "GuidePosIstUI")

    guider_min_text = f"{g_pos_min:.3f} m"
    guider_max_text = f"{g_pos_max:.3f} m"
    guider_val_text = f"{g_pos:.3f} m"

    vel_max = _param_float(params, "VelMax")
    if vel_max <= 0.0:
        vel_max = 1.0

    vel_cmd = _axis_vel_cmd(ax, vel)
    vel_cmd_min = _to_scaled_int(-vel_max)
    vel_cmd_max = _to_scaled_int(+vel_max)
    vel_cmd_val = _to_scaled_int(vel_cmd)

    user_min, user_max = _ordered_param_pair(params, "UserMin", "UserMax")
    limit_min = _to_scaled_int(user_min)
    limit_max = _to_scaled_int(user_max)
    limit_val = _to_scaled_int(pos)

    pitch = _param_float(params, "Pitch")
    denom = _PI * _DRUM_DIAMETER
    ratio = (pitch / denom) if (denom > 0.0 and pitch > 0.0) else 0.0

    g_vel_meas = _param_or_uplink(params, "GuideIstSpeed", snap, "GuideIstSpeedUI")
    g_vel_max = abs(vel_max) * ratio
    if g_vel_max <= 0.0:
        g_vel_max = 1.0
    g_vel_meas = _clamp(g_vel_meas, -g_vel_max, g_vel_max)

    guider_speed_min = _to_scaled_int(-g_vel_max)
    guider_speed_max = _to_scaled_int(+g_vel_max)
    guider_speed_val = _to_scaled_int(g_vel_meas)
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
        guider_range_min=_to_scaled_int(g_pos_min),
        guider_range_max=_to_scaled_int(g_pos_max),
        guider_range_val=_to_scaled_int(g_pos),
        guider_speed_min=int(guider_speed_min),
        guider_speed_max=int(guider_speed_max),
        guider_speed_val=int(guider_speed_val),
    )
