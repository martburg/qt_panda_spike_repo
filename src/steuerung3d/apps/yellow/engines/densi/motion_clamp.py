"""Motion clamp helpers for DenSi engine (Qt-free)."""

from __future__ import annotations

from typing import Iterable

from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState

from .setpoint_semantics import normalize_cmd_for_plant


def compute_moving_guard(*, state: MachineState, axis_ids: Iterable[str]) -> bool:
    axis_id0 = next(iter(axis_ids), "")
    ax0 = state.axes.get(axis_id0) if axis_id0 else None
    try:
        return bool(ax0 is not None and abs(float(getattr(ax0, "vel", 0.0) or 0.0)) > 1e-3)
    except Exception:
        return False


def step_plant_with_clamp(
    *,
    device: SimDevice,
    state: MachineState,
    cmd: CommandFrame,
    dt_s: float,
    axis_ids: Iterable[str],
    drive_ready: bool,
) -> None:
    cmd_for_plant = normalize_cmd_for_plant(
        cmd,
        state=state,
        dt_s=float(dt_s),
        axis_ids=list(axis_ids),
        drive_ready=bool(drive_ready),
    )
    device.step(state, cmd_for_plant, float(dt_s))


def apply_estop_clamp_to_state(*, state: MachineState) -> None:
    if bool(state.estop):
        for ax in state.axes.values():
            ax.enabled = False
            ax.vel = 0.0
