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
        # Even in SIM mode, we emulate the legacy "livetick"/"timetick" fields so that
        # the UI can display device liveness consistently.
        #
        # Semantics (SIM approximation):
        #   - lifetick_tx: a 16-bit, monotonically increasing counter in milliseconds
        #   - lifetick_rx: last lifetick value observed from the downlink (echoed back)
        #   - timetick_ms: same as lifetick_tx (legacy UI used it mostly as a liveness hint)
        step_ms = int(dt * 1000.0)
        if step_ms <= 0:
            step_ms = 1

        for axis_id, ax in state.axes.items():
            # --- device-side liveness bookkeeping (independent of motion setpoints) ---
            meta = ax.meta
            lt = int(meta.get("lifetick_tx", 0))
            lt = (lt + step_ms) & 0xFFFF
            meta["lifetick_tx"] = lt
            meta["timetick_ms"] = lt
            meta["device_tick"] = lt  # TelemetrySnapshot/HiP expects this field

            if hasattr(cmd, "lifetick_echo") and isinstance(cmd.lifetick_echo, dict):
                if axis_id in cmd.lifetick_echo:
                    meta["lifetick_rx"] = int(cmd.lifetick_echo[axis_id]) & 0xFFFF
                    # Not a strict RTT; just shows how stale the echo loop is.
                    meta["lifetick_age"] = (int(meta["lifetick_tx"]) - int(meta["lifetick_rx"])) & 0xFFFF

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
