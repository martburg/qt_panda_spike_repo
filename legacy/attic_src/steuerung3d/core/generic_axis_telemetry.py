from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from steuerung3d.core.state import MachineState, AxisState
from steuerung3d.core.core_mode import core_mode_value


@dataclass(frozen=True)
class AxisTelemetryLight:
    pos: float
    vel: float
    enabled: bool
    fault: bool


@dataclass(frozen=True)
class TelemetrySnapshot:
    tick: int
    t_s: float
    core_mode: str
    estop: bool
    fault: bool
    axes: Dict[str, AxisTelemetryLight]

    @staticmethod
    def from_state(state: MachineState) -> "TelemetrySnapshot":
        axes: Dict[str, AxisTelemetryLight] = {
            axis_id: AxisTelemetryLight(
                pos=ax.pos,
                vel=ax.vel,
                enabled=ax.enabled,
                fault=ax.fault,
            )
            for axis_id, ax in state.axes.items()
        }
        return TelemetrySnapshot(
            tick=state.tick,
            t_s=state.t_s,
            core_mode=core_mode_value(getattr(state, "core_mode", "")),
            estop=state.estop,
            fault=state.fault,
            axes=axes,
        )
