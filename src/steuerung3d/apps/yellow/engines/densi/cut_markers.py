"""Cut marker latch/clear helpers for DenSi engine (Qt-free)."""

from __future__ import annotations

from typing import Callable

from steuerung3d.core.state import MachineState


def clear_cut_markers(
    *,
    state: MachineState,
    reset_prev: bool,
    prev_estop_state: bool,
) -> tuple[bool, float, float, float, str, bool]:
    cut_valid = False
    cut_pos_m = 0.0
    cut_vel_mps = 0.0
    cut_time_s = 0.0
    systemtime_tok = ""
    if reset_prev:
        prev_estop_state = bool(getattr(state, "estop", False))

    try:
        state.params["CutPos"] = 0.0
        state.params["CutVel"] = 0.0
        state.params["CutTime"] = 0.0
        state.params["PosDiffFor"] = 0.0
    except Exception:
        pass

    return cut_valid, cut_pos_m, cut_vel_mps, cut_time_s, systemtime_tok, prev_estop_state


def maybe_latch_cut_markers(
    *,
    state: MachineState,
    axis_ids: list[str],
    estop_edge: bool,
    cut_valid: bool,
    now_token: Callable[[], str],
    cut_pos_m: float,
    cut_vel_mps: float,
    cut_time_s: float,
    systemtime_tok: str,
) -> tuple[bool, float, float, float, str]:
    if bool(estop_edge) and (not bool(cut_valid)):
        axis_id = axis_ids[0] if axis_ids else ""
        ax0 = state.axes.get(axis_id) if axis_id else None
        if ax0 is not None:
            cut_valid = True
            cut_pos_m = float(getattr(ax0, "pos", 0.0) or 0.0)
            cut_vel_mps = float(getattr(ax0, "vel", 0.0) or 0.0)
            cut_time_s = float(getattr(state, "t_s", 0.0) or 0.0)
            systemtime_tok = now_token()

            try:
                state.params["SystemTime"] = systemtime_tok
            except Exception:
                pass

            try:
                state.params["CutPos"] = float(cut_pos_m)
                state.params["CutVel"] = float(cut_vel_mps)
                state.params["CutTime"] = float(cut_time_s)
                state.params["PosDiffFor"] = 0.0
            except Exception:
                pass

    return cut_valid, cut_pos_m, cut_vel_mps, cut_time_s, systemtime_tok
