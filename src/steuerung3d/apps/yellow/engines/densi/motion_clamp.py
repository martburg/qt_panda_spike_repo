"""Motion clamp helpers for DenSi engine (Qt-free)."""

from __future__ import annotations

from typing import Iterable

from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState


def compute_moving_guard(*, state: MachineState, axis_ids: Iterable[str]) -> bool:
    """Return True if any axis is moving.

    Stable for multi-axis: treat the system as moving if *any* axis velocity
    magnitude exceeds a small threshold.
    """
    try:
        for axis_id in axis_ids:
            ax = state.axes.get(str(axis_id))
            if ax is None:
                continue
            v = float(getattr(ax, "vel", 0.0) or 0.0)
            if abs(v) > 1e-3:
                return True
        return False
    except Exception:
        return False


def step_plant_with_clamp(
    *,
    device: SimDevice,
    state: MachineState,
    cmd: CommandFrame,
    dt_s: float,
) -> None:
    device.step(state, cmd, float(dt_s))


def apply_estop_clamp_to_state(*, state: MachineState) -> None:
    if bool(state.estop):
        for ax in state.axes.values():
            ax.enabled = False
            # Do not hard-zero velocity here.
            # During E-Stop, DenSi sim models a Dcc-limited ramp-down of the
            # *actual* speed so we can compute the coastdown distance.
