from __future__ import annotations

from steuerung3d.core.intents import (
    ArmLiveMode,
    ClearFault,
    DisarmToIdle,
    EnableAxis,
    JogAxis,
    SetEstop,
    RequestEstopReset,
    ParamEditBegin,
    ParamWrite,
    ParamCancel,
    Intent,
)
from steuerung3d.core.mode import Mode
from steuerung3d.core.state import MachineState
from steuerung3d.core.command_frame import ParamEditBeginOp, ParamWriteOp, ParamCancelOp
from steuerung3d.core.state_machine import enforce_mode_actions, normalize_mode




def _enforce_pos_chain(vals: dict[str, float]) -> dict[str, float]:
    """Enforce HardMax>=UserMax>=UserMin>=HardMin."""
    keys = ('HardMax','UserMax','UserMin','HardMin')
    if not all(k in vals for k in keys):
        return vals
    hard_max = float(vals['HardMax']); hard_min = float(vals['HardMin'])
    user_max = float(vals['UserMax']); user_min = float(vals['UserMin'])
    if hard_max < hard_min:
        hard_max, hard_min = hard_min, hard_max
    user_max = max(hard_min, min(hard_max, user_max))
    user_min = max(hard_min, min(user_max, user_min))
    vals['HardMax']=hard_max; vals['HardMin']=hard_min; vals['UserMax']=user_max; vals['UserMin']=user_min
    return vals


def _enforce_guider_minmax(vals: dict[str, float]) -> dict[str, float]:
    """Enforce PosMin < PosMax."""
    if 'PosMin' not in vals or 'PosMax' not in vals:
        return vals
    mn = float(vals['PosMin']); mx = float(vals['PosMax'])
    if mn > mx:
        mn, mx = mx, mn
    if mn == mx:
        mx = mn + max(1e-6, abs(mn)*1e-6)
    vals['PosMin']=mn; vals['PosMax']=mx
    return vals

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

        # --- PARAMETERS (axis-agnostic v0.1) ---
        # These are intentionally NOT mode-gated yet.
        # The device can decide to accept/reject, and will reflect status in telemetry.
        case ParamEditBegin(group=grp):
            state.pending_param_ops.append(ParamEditBeginOp(group=grp))
            return

        case ParamWrite(group=grp, values=vals):
            cleaned = {str(k): float(v) for k, v in dict(vals).items()}
            if grp == "pos":
                cleaned = _enforce_pos_chain(cleaned)
            elif grp == "guider":
                cleaned = _enforce_guider_minmax(cleaned)
            state.pending_param_ops.append(ParamWriteOp(group=grp, values=cleaned))
            return

        case ParamCancel(group=grp):
            state.pending_param_ops.append(ParamCancelOp(group=grp))
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
