# src/steuerung3d/core/telemetry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from steuerung3d.core.mode import Mode
from steuerung3d.core.state import AxisState, MachineState

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

    # NEW
    estop_status_word: int = 0

    @classmethod
    def from_state(cls, state: MachineState) -> "TelemetrySnapshot":
        axes = {
            axis_id: AxisTelemetry(
                pos=float(ax.pos),
                vel=float(ax.vel),
                enabled=bool(ax.enabled),
                fault=bool(ax.fault),
            )
            for axis_id, ax in state.axes.items()
        }
        return cls(
            tick=int(state.tick),
            t_s=float(state.t_s),
            mode=state.mode.value if hasattr(state.mode, "value") else str(state.mode),
            estop=bool(state.estop),
            fault=bool(state.fault),
            axes=axes,
            estop_status_word=int(getattr(state, "estop_status_word", 0)),
        )

def apply_measured_snapshot(state: MachineState, snap: TelemetrySnapshot) -> None:
    state.mode = Mode(snap.mode) if isinstance(snap.mode, str) else snap.mode
    state.estop = bool(snap.estop)
    state.fault = bool(snap.fault)

    # NEW: carry the word through the core
    state.estop_status_word = int(getattr(snap, "estop_status_word", 0))

    for axis_id, ax_t in snap.axes.items():
        ax: AxisState = state.ensure_axis(axis_id)
        ax.pos = float(ax_t.pos)
        ax.vel = float(ax_t.vel)
        ax.enabled = bool(ax_t.enabled)
        ax.fault = bool(ax_t.fault)
