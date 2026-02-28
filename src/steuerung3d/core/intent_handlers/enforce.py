from __future__ import annotations

from steuerung3d.core.core_mode import CoreMode, core_mode_value
from steuerung3d.core.state import MachineState


def enforce_core_mode_actions(state: MachineState) -> None:
    """Apply mode-derived safety clamps to the current command state."""
    core_mode = core_mode_value(getattr(state, "core_mode", "")).upper()
    if core_mode == CoreMode.ESTOP.value:
        for cmd in state.axis_cmd.values():
            cmd.enable = False
            cmd.vel = 0.0
        return
    if core_mode in (CoreMode.FAULT.value, CoreMode.IDLE.value, CoreMode.ARMED.value, CoreMode.READY.value):
        for cmd in state.axis_cmd.values():
            cmd.vel = 0.0
        return
