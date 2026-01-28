from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState


@dataclass
class AxisPlantParams:
    max_vel: float = 5.0  # units/s
    max_acc: float = 5.0  # units/s^2


@dataclass
class SimAxisPlant:
    """Very small device-layer simulation.

    The *core* produces a :class:`~steuerung3d.core.command_frame.CommandFrame`.
    The sim "device" consumes it and updates the measured state in-place.

    Measured (device -> core telemetry):
      - `AxisState.enabled/vel/pos/fault`

    Commanded (core -> device setpoints):
      - `CommandFrame.axes[axis_id].enable`
      - `CommandFrame.axes[axis_id].vel`

    Notes:
      - This is intentionally simple: no position control, no current/torque model, no limits
        besides max velocity and max acceleration.
      - Safety is handled in core (mode clamps), but we still treat missing setpoints as "disable".
    """

    params: Dict[str, AxisPlantParams] = field(default_factory=dict)
    default: AxisPlantParams = field(default_factory=AxisPlantParams)

    def step(self, state: MachineState, cmd: CommandFrame, dt: float) -> None:
        for axis_id, ax in state.axes.items():
            p = self.params.get(axis_id, self.default)

            sp = cmd.axes.get(axis_id)
            if sp is None:
                # no setpoint => stop & disable
                ax.enabled = False
                ax.vel = 0.0
                continue

            ax.enabled = bool(sp.enable)
            if not ax.enabled:
                ax.vel = 0.0
                continue

            # Clamp desired velocity
            v_des = float(sp.vel)
            if v_des > p.max_vel:
                v_des = p.max_vel
            elif v_des < -p.max_vel:
                v_des = -p.max_vel

            # Acceleration-limited velocity tracking
            dv = v_des - ax.vel
            dv_max = p.max_acc * dt
            if dv > dv_max:
                dv = dv_max
            elif dv < -dv_max:
                dv = -dv_max

            ax.vel += dv
            ax.pos += ax.vel * dt
