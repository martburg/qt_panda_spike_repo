from __future__ import annotations

from steuerung3d.core.mode import Mode
from steuerung3d.core.state import MachineState

def _coerce_mode(val) -> Mode:
    if isinstance(val, Mode):
        return val
    if val is None:
        return Mode.IDLE
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("Mode."):
            s = s.split(".", 1)[1]
        s = s.upper()
        # Mode is a str Enum with values like "IDLE"
        try:
            return Mode(s)
        except Exception:
            return Mode.IDLE
    return Mode.IDLE


def normalize_mode(state: MachineState) -> None:
    """
    Enforce invariant priority:
      ESTOP > FAULT > (IDLE/LIVE)
    """
    state.mode = _coerce_mode(getattr(state, "mode", None))
    
    if state.estop:
        state.mode = Mode.ESTOP
        return
    if state.fault:
        state.mode = Mode.FAULT
        return
    # if we were in ESTOP/FAULT and the condition cleared, fall back to IDLE
    if state.mode in (Mode.ESTOP, Mode.FAULT):
        state.mode = Mode.IDLE


def enforce_mode_actions(state: MachineState) -> None:
    normalize_mode(state)

    if state.mode == Mode.ESTOP:
        for cmd in state.axis_cmd.values():
            cmd.enable = False
            cmd.vel = 0.0
        return

    if state.mode == Mode.FAULT:
        for cmd in state.axis_cmd.values():
            cmd.vel = 0.0
        return

    if state.mode == Mode.IDLE:
        for cmd in state.axis_cmd.values():
            cmd.vel = 0.0
        return

    # LIVE: no forced action
    if state.mode == Mode.LIVE:
        return