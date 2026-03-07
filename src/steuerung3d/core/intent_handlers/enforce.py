from __future__ import annotations

from steuerung3d.core.core_mode import CoreMode, core_mode_value
from steuerung3d.core.joy_state import canonicalize_selected_axes
from steuerung3d.core.motion_gate import axis_local_motion_allowed
from steuerung3d.core.state import MachineState


def enforce_core_mode_actions(state: MachineState) -> None:
    """Apply mode-derived safety clamps to the current command state."""
    core_mode = core_mode_value(getattr(state, "core_mode", "")).upper()
    if core_mode == CoreMode.ESTOP.value:
        for cmd in state.axis_cmd.values():
            cmd.enable = False
            cmd.vel = 0.0
        return
    if core_mode in (CoreMode.FAULT.value, CoreMode.IDLE.value):
        for cmd in state.axis_cmd.values():
            cmd.vel = 0.0
        return
    if core_mode in (CoreMode.ARMED.value, CoreMode.READY.value):
        joy = getattr(state, "joy", None)
        joy_deadman = bool(getattr(joy, "deadman", False)) if joy is not None else False
        selected_axes = set(canonicalize_selected_axes(getattr(joy, "selected_axes", ()))) if joy is not None else set()
        for axis_id, cmd in state.axis_cmd.items():
            keep_local = bool(joy_deadman) and (axis_id in selected_axes) and axis_local_motion_allowed(state, axis_id)
            if not keep_local:
                cmd.vel = 0.0
        return
