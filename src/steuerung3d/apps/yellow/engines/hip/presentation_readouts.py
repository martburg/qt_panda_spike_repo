from __future__ import annotations

from typing import Mapping

from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot

from ...domain.ui_format import fmt_f_unit, fmt_i_unit
from .presentation_extract import raw_uplink_float
from .viewmodel import HipReadoutsState


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

    try:
        g_pos_min = float(params.get("PosMin", 0.0) or 0.0)
    except Exception:
        g_pos_min = 0.0
    try:
        g_pos_max = float(params.get("PosMax", 0.0) or 0.0)
    except Exception:
        g_pos_max = 0.0
    if g_pos_max < g_pos_min:
        g_pos_min, g_pos_max = g_pos_max, g_pos_min

    try:
        g_pos = float(params.get("GuidePosIst", 0.0) or 0.0)
    except Exception:
        g_pos = 0.0
    if g_pos == 0.0:
        g_pos = raw_uplink_float(snap, "GuidePosIstUI", g_pos)

    guider_min_text = f"{g_pos_min:.3f} m"
    guider_max_text = f"{g_pos_max:.3f} m"
    guider_val_text = f"{g_pos:.3f} m"

    try:
        vel_max = float(params.get("VelMax", 0.0) or 0.0)
    except Exception:
        vel_max = 0.0
    if vel_max <= 0.0:
        vel_max = 1.0

    try:
        vel_cmd = float(getattr(ax, "vel_cmd", vel) if ax is not None else vel)
    except Exception:
        vel_cmd = vel
    scale = 1000.0
    vel_cmd_min = int(round(-vel_max * scale))
    vel_cmd_max = int(round(+vel_max * scale))
    vel_cmd_val = int(round(vel_cmd * scale))

    try:
        user_min = float(params.get("UserMin", 0.0) or 0.0)
    except Exception:
        user_min = 0.0
    try:
        user_max = float(params.get("UserMax", 0.0) or 0.0)
    except Exception:
        user_max = 0.0
    if user_max < user_min:
        user_min, user_max = user_max, user_min
    limit_min = int(round(user_min * scale))
    limit_max = int(round(user_max * scale))
    limit_val = int(round(pos * scale))

    drum_diam = 0.5
    try:
        pitch = float(params.get("Pitch", 0.0) or 0.0)
    except Exception:
        pitch = 0.0
    denom = 3.141592653589793 * drum_diam
    ratio = (pitch / denom) if (denom > 0.0 and pitch > 0.0) else 0.0

    try:
        g_vel_meas = float(params.get("GuideIstSpeed", 0.0) or 0.0)
    except Exception:
        g_vel_meas = 0.0
    if g_vel_meas == 0.0:
        g_vel_meas = raw_uplink_float(snap, "GuideIstSpeedUI", g_vel_meas)

    g_vel_max = abs(vel_max) * ratio
    if g_vel_max <= 0.0:
        g_vel_max = 1.0
    if g_vel_meas > g_vel_max:
        g_vel_meas = g_vel_max
    elif g_vel_meas < -g_vel_max:
        g_vel_meas = -g_vel_max

    guider_speed_min = int(round(-g_vel_max * scale))
    guider_speed_max = int(round(+g_vel_max * scale))
    guider_speed_val = int(round(g_vel_meas * scale))
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
        guider_range_min=int(round(g_pos_min * scale)),
        guider_range_max=int(round(g_pos_max * scale)),
        guider_range_val=int(round(g_pos * scale)),
        guider_speed_min=int(guider_speed_min),
        guider_speed_max=int(guider_speed_max),
        guider_speed_val=int(guider_speed_val),
    )
