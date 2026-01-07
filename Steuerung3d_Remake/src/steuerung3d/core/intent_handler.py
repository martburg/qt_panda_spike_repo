from __future__ import annotations

from steuerung3d.core.intents import (
    ArmLiveMode,
    ClearFault,
    DisarmToIdle,
    EnableAxis,
    JogAxis,
    SetEstop,
    Intent,
)
from steuerung3d.core.mode import Mode
from steuerung3d.core.state import MachineState
from steuerung3d.core.state_machine import enforce_mode_actions, normalize_mode


def apply_intent(state: MachineState, intent: Intent) -> None:
    """Apply an intent to MachineState.

    v0.1 policy:
      - Safety/mode intents always apply.
      - Motion/control intents only apply in LIVE.
      - Commands are stored in `state.axis_cmd` (commanded), while `state.axes` is measured.

    Later this becomes: Intent -> Planner -> Safety -> CommandFrame.
    """

    # --- global intents: can always be applied ---
    if isinstance(intent, SetEstop):
        state.estop = bool(intent.estop)
        normalize_mode(state)
        enforce_mode_actions(state)

        # UX nicety: when ESTOP engages, immediately clamp measured motion too.
        # (In the real system the device would report this on the next telemetry update.)
        if state.mode == Mode.ESTOP:
            for ax in state.axes.values():
                ax.enabled = False
                ax.vel = 0.0
        return

    if isinstance(intent, ClearFault):
        state.fault = False
        for ax in state.axes.values():
            ax.fault = False
        normalize_mode(state)
        enforce_mode_actions(state)
        return

    # --- mode transitions ---
    if isinstance(intent, ArmLiveMode):
        normalize_mode(state)
        if state.mode == Mode.IDLE and (not state.estop) and (not state.fault):
            state.mode = Mode.LIVE
        enforce_mode_actions(state)
        return

    if isinstance(intent, DisarmToIdle):
        normalize_mode(state)
        if state.mode == Mode.LIVE:
            state.mode = Mode.IDLE
        enforce_mode_actions(state)
        return

    # --- mode-gated intents ---
    normalize_mode(state)

    if state.mode != Mode.LIVE:
        # In v0.1: only LIVE accepts motion/control intents
        enforce_mode_actions(state)
        return

    # LIVE mode logic
    if isinstance(intent, EnableAxis):
        state.ensure_axis(intent.axis_id)
        cmd = state.ensure_axis_cmd(intent.axis_id)
        cmd.enable = bool(intent.enable)
        if not cmd.enable:
            cmd.vel = 0.0
        return

    if isinstance(intent, JogAxis):
        state.ensure_axis(intent.axis_id)
        cmd = state.ensure_axis_cmd(intent.axis_id)
        if cmd.enable:
            cmd.vel = float(intent.vel)
        return
