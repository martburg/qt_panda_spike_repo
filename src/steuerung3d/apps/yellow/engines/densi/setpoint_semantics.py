"""DenSi command-frame normalization for plant stepping (Qt-free)."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot


def normalize_cmd_for_plant(
    cmd: CommandFrame,
    *,
    state: MachineState,
    dt_s: float,
    axis_ids: Iterable[str] | None = None,
    drive_ready: bool = True,
    snap: TelemetrySnapshot | None = None,
) -> CommandFrame:
    """Return the command frame that should be applied to the DenSi plant.

    This is a pass-through unless DenSi must clamp motion, in which case all
    axes are disabled with zero velocity (matching prior behavior).
    """
    _ = (dt_s, snap)
    if bool(drive_ready) and (not bool(state.estop)):
        return cmd

    axes = axis_ids if axis_ids is not None else list(cmd.axes.keys())
    return replace(
        cmd,
        axes={str(a): AxisSetpoint(enable=False, vel=0.0) for a in axes},
    )
