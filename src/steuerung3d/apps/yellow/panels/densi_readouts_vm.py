"""DenSi readouts view-model (Qt-free).

This is intentionally *pure* and importable in headless unit tests.
It computes the values that the DenSi UI should display.

Semantics are preserved by copying the logic from the legacy
`DenSiController._render_live_readouts_ui` implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState

from ..domain.ui_format import fmt_f_unit, fmt_i_unit


@dataclass(frozen=True)
class DenSiReadoutsVM:
    # --- numerics (also useful for downstream computations like cut markers) ---
    axis_id: str
    pos_m: float
    vel_mps: float

    # --- primary readouts ---
    pos_text: str
    vel_text: str
    amp_text: str
    temp_text: str

    # --- guider readouts ---
    guider_min_text: str
    guider_max_text: str
    guider_val_text: str
    guider_speed_text: str

    # --- slider indicators ---
    # sldVelCmd: commanded velocity mapped to an integer slider range
    vel_cmd_min: int
    vel_cmd_max: int
    vel_cmd_val: int

    # sldLimitRange: current position mapped into [UserMin, UserMax]
    limit_min: int
    limit_max: int
    limit_val: int


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def compute_densi_readouts_vm(
    *,
    state: MachineState,
    axis_id: str,
    last_cmd: CommandFrame | None,
) -> DenSiReadoutsVM:
    """Compute DenSi live readouts + slider targets.

    Inputs:
      - state: DenSi's MachineState (simulated device)
      - axis_id: the (single) axis shown in DenSi
      - last_cmd: last CommandFrame received (may be None)
    """

    ax = state.axes.get(axis_id) if axis_id else None
    pos = _safe_float(getattr(ax, "pos", 0.0) if ax else 0.0)
    vel = _safe_float(getattr(ax, "vel", 0.0) if ax else 0.0)

    amp = _safe_float(state.params.get("ActCur", 0.0), 0.0)
    tmp = _safe_float(state.params.get("Temp", 20.0), 20.0)

    pos_text = fmt_f_unit(pos, "m", ndigits=2)
    vel_text = fmt_f_unit(vel, "m/s", ndigits=2)
    amp_text = fmt_i_unit(int(round(amp)), "A")
    temp_text = fmt_i_unit(int(round(tmp)), "°")

    # Guider readouts (defaults if not yet modeled)
    g_min = _safe_float(state.params.get("PosMin", 0.0) or 0.0)
    g_max = _safe_float(state.params.get("PosMax", 0.0) or 0.0)
    g_val = _safe_float(state.params.get("GuidePosIst", 0.0) or 0.0)
    g_spd = _safe_float(state.params.get("GuideIstSpeed", 0.0) or 0.0)

    guider_min_text = fmt_f_unit(g_min, "m", ndigits=3)
    guider_max_text = fmt_f_unit(g_max, "m", ndigits=3)
    guider_val_text = fmt_f_unit(g_val, "m", ndigits=3)
    guider_speed_text = f"{g_spd:.3f} m/s"

    # --- slider indicators ---
    # sldVelCmd: show commanded velocity (setpoint) with range ±VelMax
    vel_max = _safe_float(state.params.get("VelMax", 0.0) or 0.0)
    if vel_max <= 0.0:
        vel_max = 1.0

    vel_cmd = 0.0
    try:
        if last_cmd is not None and axis_id and hasattr(last_cmd, "axes"):
            sp = last_cmd.axes.get(axis_id)
            if sp is not None:
                vel_cmd = _safe_float(getattr(sp, "vel", 0.0), 0.0)
    except Exception:
        vel_cmd = 0.0

    scale_v = 1000.0  # m/s -> mm/s for slider resolution
    vel_cmd_min = int(round(-vel_max * scale_v))
    vel_cmd_max = int(round(+vel_max * scale_v))
    vel_cmd_val = int(round(vel_cmd * scale_v))

    # sldLimitRange: show current position in [UserMin, UserMax]
    user_min = _safe_float(state.params.get("UserMin", 0.0) or 0.0)
    user_max = _safe_float(state.params.get("UserMax", 0.0) or 0.0)
    if user_max < user_min:
        user_min, user_max = user_max, user_min

    scale_p = 1000.0  # m -> mm for slider resolution
    limit_min = int(round(user_min * scale_p))
    limit_max = int(round(user_max * scale_p))
    limit_val = int(round(pos * scale_p))

    return DenSiReadoutsVM(
        axis_id=str(axis_id or ""),
        pos_m=float(pos),
        vel_mps=float(vel),
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
    )
