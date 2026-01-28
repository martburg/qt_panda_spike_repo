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
        estop=False,  # <-- important policy change
        fault=state.fault,
        mode=state.mode.value,
        axes=axes,
        estop_reset=state.estop_reset_req,  # pulse from HI-P intent
        param_ops=list(getattr(state, "pending_param_ops", [])),
    )