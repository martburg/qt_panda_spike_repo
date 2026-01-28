from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState


@dataclass
class SimDevice:
    plant: SimAxisPlant

    def step(self, state: MachineState, cmd: CommandFrame, dt: float) -> None:
        self.plant.step(state, cmd, dt)
