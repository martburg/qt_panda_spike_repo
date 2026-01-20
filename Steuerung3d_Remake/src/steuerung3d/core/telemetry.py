from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from steuerung3d.core.state import MachineState, AxisState

from steuerung3d.core.mode import Mode


@dataclass(frozen=True)
class AxisTelemetry:
    pos: float
    vel: float
    enabled: bool
    fault: bool


@dataclass(frozen=True)
class TelemetrySnapshot:
    tick: int
    t_s: float
    mode: str
    estop: bool
    fault: bool
    axes: Dict[str, AxisTelemetry]

    @staticmethod
    def from_state(state: MachineState) -> "TelemetrySnapshot":
        axes: Dict[str, AxisTelemetry] = {
            axis_id: AxisTelemetry(
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
            mode=state.mode.value,
            estop=state.estop,
            fault=state.fault,
            axes=axes,
        )
    
def apply_measured_snapshot(state: MachineState, snap: TelemetrySnapshot) -> None:
    state.estop = bool(snap.estop)
    state.fault = bool(snap.fault)
    state.mode = Mode(snap.mode) if isinstance(snap.mode, str) else snap.mode  # depending on your snapshot

    for axis_id, ax_t in snap.axes.items():
        ax = state.ensure_axis(axis_id)
        ax.pos = ax_t.pos
        ax.vel = ax_t.vel
        ax.enabled = ax_t.enabled
        ax.fault = ax_t.fault