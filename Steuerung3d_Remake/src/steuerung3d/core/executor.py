from __future__ import annotations

from typing import Dict

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.core.state import MachineState


def build_command_frame(state: MachineState) -> CommandFrame:
    axes: Dict[str, AxisSetpoint] = {
        axis_id: AxisSetpoint(enable=cmd.enable, vel=cmd.vel)
        for axis_id, cmd in state.axis_cmd.items()
    }
    return CommandFrame(
        tick=state.tick,
        t_s=state.t_s,
        estop=state.estop,
        fault=state.fault,
        mode=state.mode.value,
        axes=axes,
    )
