"""PLC-faithful DenSi velocity command reaction (Anton).

Implementation step contract (see docs/anton_vel_cmd_implementation_step.md):
- Gate motion by intent/enable, safety-ready, and lifetick staleness.
- Clamp SpeedSollIN to SpeedMaxUI.
- Apply soft-limit braking using sqrt(DccMaxUI * PosDiff).
- Ramp velocity using AccTotUI/AccMaxUI.
- Apply position-trim PID overlay (FilterP/I/D/IL).
- Keep deterministic, tick-based semantics only.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.common.staleness import age_ticks, is_stale

from .param_defaults import apply_densi_param_defaults


@dataclass(frozen=True)
class PlcAntonVelCmdConfig:
    lifetick_stale_after_ticks_active: int = 50
    lifetick_stale_after_ticks_idle: int = 500


def _f(params: dict[str, float], key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except Exception:
        return float(default)


def _f_any(params: dict[str, float], keys: list[str], default: float) -> float:
    for k in keys:
        if k in params:
            return _f(params, k, default)
    return float(default)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _soft_limit_cap(
    *,
    v: float,
    pos: float,
    user_min: float,
    user_max: float,
    dcc_max: float,
) -> float:
    if v > 0.0:
        dist = float(user_max) - float(pos)
        if dist <= 0.0:
            return 0.0
        vmax = math.sqrt(max(float(dcc_max), 0.0) * dist)
        return min(v, vmax)
    if v < 0.0:
        dist = float(pos) - float(user_min)
        if dist <= 0.0:
            return 0.0
        vmin = -math.sqrt(max(float(dcc_max), 0.0) * dist)
        return max(v, vmin)
    return v


def _lifetick_is_stale(*, meta: dict, lifetick_rx: int, stale_after_ticks: int) -> bool:
    step_tick = int(meta.get("plc_lifetick_step_tick", 0)) + 1
    meta["plc_lifetick_step_tick"] = int(step_tick)

    last_rx = meta.get("plc_lifetick_rx", None)
    last_rx_step = meta.get("plc_lifetick_rx_step_tick", None)

    if last_rx is None or int(lifetick_rx) != int(last_rx):
        last_rx = int(lifetick_rx) & 0xFFFF
        last_rx_step = int(step_tick)

    meta["plc_lifetick_rx"] = int(last_rx) & 0xFFFF
    meta["plc_lifetick_rx_step_tick"] = int(last_rx_step) if last_rx_step is not None else None

    age = age_ticks(step_tick, last_rx_step)
    meta["plc_lifetick_age_ticks"] = int(age or 0)
    return is_stale(step_tick, last_rx_step, int(stale_after_ticks))


def _pid_trim(
    *,
    meta: dict,
    pos_soll: float,
    pos_ist: float,
    p: float,
    i: float,
    d: float,
    il: float,
    dt_s: float,
) -> float:
    pos_err = float(pos_soll) - float(pos_ist)
    err_int = float(meta.get("plc_pos_err_int", 0.0)) + (pos_err * float(dt_s))
    prev_err = float(meta.get("plc_pos_err_prev", pos_err))
    err_d = pos_err - prev_err

    meta["plc_pos_err_int"] = float(err_int)
    meta["plc_pos_err_prev"] = float(pos_err)

    filt = (float(p) * pos_err) + (float(i) * err_int) + (float(d) * err_d)
    if float(il) > 0.0:
        filt = _clamp(filt, -float(il), float(il))
    return float(filt)


def step_plc_anton_vel_cmd(
    *,
    state: MachineState,
    cmd: CommandFrame,
    dt_s: float,
    axis_ids: Iterable[str],
    ready_for_sollvel: bool,
    lifetick_stale_after_ticks_active: int,
    lifetick_stale_after_ticks_idle: int,
    deadman_active: bool,
    ramp_mode_ok: bool,
) -> None:
    params = dict(getattr(state, "params", {}) or {})
    for axis_id in axis_ids:
        ax = state.ensure_axis(str(axis_id))
        sp = (getattr(cmd, "axes", {}) or {}).get(axis_id)

        enable_cmd = bool(getattr(sp, "enable", False)) if sp is not None else False
        intent_ok = bool(getattr(cmd, "intent", True))
        control_enabled = bool(enable_cmd) and bool(intent_ok) and bool(ready_for_sollvel)
        control_enabled = control_enabled and (not bool(state.estop)) and (not bool(state.fault))

        # Lifetick echo stale gate (tick-based).
        echo_map = getattr(cmd, "lifetick_echo", {}) if isinstance(getattr(cmd, "lifetick_echo", {}), dict) else {}
        lifetick_rx = int(echo_map.get(axis_id, int(getattr(cmd, "tick", 0)))) & 0xFFFF
        stale_after = int(lifetick_stale_after_ticks_active if deadman_active else lifetick_stale_after_ticks_idle)
        stale = _lifetick_is_stale(
            meta=ax.meta,
            lifetick_rx=lifetick_rx,
            stale_after_ticks=stale_after,
        )

        # Commanded speed from SpeedSollIN (AxisSetpoint.vel).
        desired = float(getattr(sp, "vel", 0.0)) if sp is not None else 0.0
        if (not control_enabled) or stale or (not bool(ramp_mode_ok)):
            desired = 0.0

        # Clamp to SpeedMaxUI.
        speed_max = _f_any(params, ["VelMax", "SpeedMaxUI"], 0.0)
        if speed_max > 0.0:
            desired = _clamp(desired, -speed_max, speed_max)

        # Soft-limit braking (user limits).
        user_max = _f_any(params, ["UserMax", "PosMaxUserUI"], 1.0e9)
        user_min = _f_any(params, ["UserMin", "PosMinUserUI"], -1.0e9)
        dcc_max = _f_any(params, ["DccMax", "DccMaxUI"], 0.0)
        desired = _soft_limit_cap(v=desired, pos=ax.pos, user_min=user_min, user_max=user_max, dcc_max=dcc_max)

        # Acceleration ramp.
        ramped = float(ax.meta.get("plc_ramped_speed", 0.0))
        acc = _f_any(params, ["AccMove", "AccTotUI", "AccMax", "AccMaxUI"], 0.0)
        dv_max = abs(float(acc)) * float(dt_s)
        if desired > ramped:
            ramped = min(desired, ramped + dv_max)
        elif desired < ramped:
            ramped = max(desired, ramped - dv_max)
        ax.meta["plc_ramped_speed"] = float(ramped)

        # Position-trim overlay.
        pos_soll = float(getattr(sp, "pos", params.get("PosSoll", ax.pos))) if sp is not None else float(params.get("PosSoll", ax.pos))
        filt = _pid_trim(
            meta=ax.meta,
            pos_soll=pos_soll,
            pos_ist=ax.pos,
            p=_f_any(params, ["P", "FilterP"], 0.0),
            i=_f_any(params, ["I", "FilterI"], 0.0),
            d=_f_any(params, ["D", "FilterD"], 0.0),
            il=_f_any(params, ["IL", "FilterIL"], 0.0),
            dt_s=dt_s,
        )

        final_speed = float(ramped + filt)
        final_speed = _soft_limit_cap(v=final_speed, pos=ax.pos, user_min=user_min, user_max=user_max, dcc_max=dcc_max)

        ax.enabled = bool(control_enabled) and (not bool(stale))
        if not ax.enabled:
            ax.vel = 0.0
        else:
            ax.vel = float(final_speed)
            ax.pos += ax.vel * float(dt_s)

        # Keep diagnostics for UI/PLC uplink fields.
        params["PosDiffFor"] = float(pos_soll) - float(ax.pos)

        # Guide fields: keep minimal, deterministic echo.
        guide_control = int(params.get("GuideControl", 0) or 0)
        guide_speed = float(params.get("GuideSollSpeed", 0.0) or 0.0)
        if guide_control:
            params["GuideIstSpeed"] = float(guide_speed)
            params["GuidePosIst"] = float(params.get("GuidePosIst", 0.0)) + float(guide_speed) * float(dt_s)
        else:
            apply_densi_param_defaults(params, keys=("GuideIstSpeed", "GuidePosIst"))

    state.params.update(params)
