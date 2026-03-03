"""Presentation helpers for HipEngine (Qt-free)."""

from __future__ import annotations

from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.estop_bits import decode_estop_word
from steuerung3d.util.tick import compute_time_tick

from ...domain.banner_facts import derive_banner_estate_from_word
from ...domain.ui_format import fmt_f_unit, fmt_i_unit
from .viewmodel import HipCutMarkersState, HipReadoutsState

# NOTE: drive status decoder is optional.
try:
    from steuerung3d.protocol.drive_status import decode_drive_status  # type: ignore
except Exception:  # pragma: no cover
    decode_drive_status = None  # type: ignore


def compute_banner_estate(*, estop_word: int, within_brake_grace: bool) -> str:
    return derive_banner_estate_from_word(
        int(estop_word),
        within_brake_grace=lambda: bool(within_brake_grace),
    )


def compute_tick_text(
    *,
    snap: TelemetrySnapshot,
    axis_id: str,
    prev_device_tick: int | None,
) -> tuple[str, int | None]:
    if not axis_id:
        return "--", None

    axes = getattr(snap, "axes", None)
    if not isinstance(axes, dict):
        return "--", None

    ax = axes.get(axis_id)
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
    axes = getattr(snap, "axes", None)
    if not isinstance(axes, dict):
        return None
    ax = axes.get(axis_id)
    if ax is None:
        return None
    try:
        return int(getattr(ax, "lifetick_age", 0) or 0)
    except Exception:
        return None


def parse_estop_word_from_snapshot(snap: TelemetrySnapshot) -> int:
    fields = getattr(snap, "plc_uplink_fields", None)
    if isinstance(fields, dict):
        v = fields.get("EStopStatus")
        if v is not None:
            try:
                return int(str(v).strip())
            except Exception:
                pass
    return int(getattr(snap, "estop_status_word", 0) or 0)


def raw_uplink_float(snap: TelemetrySnapshot, key: str, default: float) -> float:
    try:
        raw = getattr(snap, "plc_uplink_fields", None)
        if isinstance(raw, dict) and key in raw:
            return float(raw.get(key, default) or default)
    except Exception:
        pass
    return float(default)


def raw_tail_token(snap: TelemetrySnapshot, key: str) -> str:
    try:
        tail = getattr(snap, "plc_uplink_tail", {}) or {}
        if isinstance(tail, dict):
            v = tail.get(key, "") or ""
            return str(v)
    except Exception:
        pass
    return ""


def read_axis_pos_vel(ax) -> tuple[float, float]:
    try:
        pos = float(getattr(ax, "pos", 0.0) or 0.0)
    except Exception:
        pos = 0.0
    try:
        vel = float(getattr(ax, "vel", 0.0) or 0.0)
    except Exception:
        vel = 0.0
    return pos, vel


def read_amp_and_temp(*, params: dict, snap: TelemetrySnapshot) -> tuple[float, float]:
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


def compute_readouts_state(
    *,
    ax,
    pos: float,
    vel: float,
    amp: float,
    temp: float,
    params: dict,
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


def compute_cut_markers_state(
    *,
    snap: TelemetrySnapshot,
    params: dict,
    estate: str,
    mode: str,
) -> HipCutMarkersState:
    try:
        cut_pos = float(params.get("CutPos", 0.0) or 0.0)
        cut_vel = float(params.get("CutVel", 0.0) or 0.0)
        posdiff = float(params.get("PosDiffFor", 0.0) or 0.0)
    except Exception:
        cut_pos = 0.0
        cut_vel = 0.0
        posdiff = 0.0

    in_estop = bool(getattr(snap, "estop", False))
    try:
        word = parse_estop_word_from_snapshot(snap)
        bits = decode_estop_word(int(word))
        in_estop = any(
            bool(bits.get(k, False)) for k in ("master", "slave", "network", "estop1", "estop2")
        )
    except Exception:
        pass
    if not in_estop and str(estate or "").upper() == "ESTOP":
        in_estop = True
    mode_u = str(mode or "").upper()
    in_sync = mode_u.startswith("SYNC")

    # Show cut markers in IDLE and ESTOP, but hide them while in SYNC_* modes.
    if in_sync:
        cut_pos_text = "--"
        cut_vel_text = "--"
        posdiff_text = "--"
    else:
        cut_pos_text = fmt_f_unit(cut_pos, "m", ndigits=2)
        cut_vel_text = fmt_f_unit(cut_vel, "m/s", ndigits=2)
        posdiff_text = fmt_f_unit(posdiff, "m", ndigits=2)

    t_tok = raw_tail_token(snap, "SystemTime")
    cut_time_text = t_tok if t_tok else "--"
    return HipCutMarkersState(
        cut_time_text=str(cut_time_text),
        cut_pos_text=str(cut_pos_text),
        cut_vel_text=str(cut_vel_text),
        posdiff_text=str(posdiff_text),
    )


def compute_drive_status_texts(*, snap: TelemetrySnapshot, axis_id: str) -> tuple[str, str]:
    if decode_drive_status is None:
        return "", ""
    if not axis_id:
        return "", ""
    axes = getattr(snap, "axes", None)
    if not isinstance(axes, dict):
        return "", ""
    ax = axes.get(axis_id)
    if ax is None:
        return "", ""
    main_word = int(getattr(ax, "status_word", 0) or 0)
    slave_word = int(getattr(ax, "guide_status_word", 0) or 0)
    try:
        main = decode_drive_status(main_word)
        slave = decode_drive_status(slave_word)
        return str(main.summary()), str(slave.summary())
    except Exception:
        return "", ""


def compute_drive_status_summary(*, snap: TelemetrySnapshot, axis_id: str) -> str:
    if decode_drive_status is None:
        return ""
    if not axis_id:
        return ""
    axes = getattr(snap, "axes", None)
    if not isinstance(axes, dict):
        return ""
    ax = axes.get(axis_id)
    if ax is None:
        return ""
    main_word = int(getattr(ax, "status_word", 0) or 0)
    slave_word = int(getattr(ax, "guide_status_word", 0) or 0)
    try:
        main = decode_drive_status(main_word)
        slave = decode_drive_status(slave_word)
        return f"{main.summary()}|{slave.summary()}"
    except Exception:
        return ""
