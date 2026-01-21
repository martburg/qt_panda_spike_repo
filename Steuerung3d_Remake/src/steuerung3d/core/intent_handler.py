from __future__ import annotations

from steuerung3d.core.intents import (
    ArmLiveMode,
    ClearFault,
    DisarmToIdle,
    EnableAxis,
    JogAxis,
    SetEstop,
    RequestEstopReset,
    Intent,
)
from steuerung3d.core.mode import Mode
from steuerung3d.core.state import MachineState
from steuerung3d.core.state_machine import enforce_mode_actions, normalize_mode


def apply_intent(state: MachineState, intent: Intent) -> None:
    """
    Apply an intent to MachineState.

    Policy (now, with latched ESTOP):
      - ESTOP state is device-authoritative (measured via telemetry).
      - Operator can request a reset (pulse) via RequestEstopReset.
      - Fault clear is still a core-side request (later also device-verified).
      - Motion/control intents only apply in LIVE.
    """

    match intent:
        # --- SAFETY / GLOBAL REQUESTS ---
        case RequestEstopReset():
            # one-tick pulse; CoreEngine should clear it after building/sending command frame
            state.estop_reset_req = True
            # do NOT change state.estop here (device owns it)
            normalize_mode(state)
            enforce_mode_actions(state)
            return

        case SetEstop(estop=val):
            state.estop = bool(val)
            normalize_mode(state)
            enforce_mode_actions(state)
            if state.mode == Mode.ESTOP:
                for ax in state.axes.values():
                    ax.enabled = False
                    ax.vel = 0.0
            return

        case ClearFault():
            # still okay as a core-side request; later: device-side fault latch too
            state.fault = False
            for ax in state.axes.values():
                ax.fault = False
            normalize_mode(state)
            enforce_mode_actions(state)
            return

        # --- MODE TRANSITIONS ---
        case ArmLiveMode():
            normalize_mode(state)
            if state.mode == Mode.IDLE and (not state.estop) and (not state.fault):
                state.mode = Mode.LIVE
            enforce_mode_actions(state)
            return

        case DisarmToIdle():
            normalize_mode(state)
            if state.mode == Mode.LIVE:
                state.mode = Mode.IDLE
            enforce_mode_actions(state)
            return

        # fallthrough to mode-gated below
        case _:
            pass

    # --- MODE-GATED INTENTS (LIVE only) ---
    normalize_mode(state)

    if state.mode != Mode.LIVE:
        enforce_mode_actions(state)
        return

    match intent:
        case EnableAxis(axis_id=axis_id, enable=enable):
            state.ensure_axis(axis_id)
            cmd = state.ensure_axis_cmd(axis_id)
            cmd.enable = bool(enable)
            if not cmd.enable:
                cmd.vel = 0.0
            return

        case JogAxis(axis_id=axis_id, vel=vel):
            state.ensure_axis(axis_id)
            cmd = state.ensure_axis_cmd(axis_id)
            if cmd.enable:
                cmd.vel = float(vel)
            return

        case _:
            return
