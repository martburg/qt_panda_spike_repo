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



def _txn_ack(state: MachineState, req_id: str) -> None:
    """Record a one-shot ack for HIP (emitted in telemetry)."""
    if req_id:
        state.core_acks.append(req_id)

def _txn_seen_or_mark(state: MachineState, req_id: str, *, max_keep: int = 512) -> bool:
    """Return True if req_id was seen before; else mark it as seen.

    We keep a bounded map (req_id -> last_seen_tick) to prevent unbounded growth.
    """
    if not req_id:
        return False
    if req_id in state.seen_req_ids:
        state.seen_req_ids[req_id] = int(state.tick)
        return True
    state.seen_req_ids[req_id] = int(state.tick)
    if len(state.seen_req_ids) > max_keep:
        # drop oldest entries
        items = sorted(state.seen_req_ids.items(), key=lambda kv: kv[1])
        for k, _t in items[: len(items) - max_keep]:
            state.seen_req_ids.pop(k, None)
    return False


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
        case ParamEditBegin(group=grp, req_id=req_id, session_id=session_id):
            _txn_ack(state, req_id)
            if _txn_seen_or_mark(state, req_id):
                return
            state.pending_param_ops.append(ParamEditBeginOp(group=grp))
            return

        case ParamWrite(group=grp, values=vals, req_id=req_id, session_id=session_id):
            _txn_ack(state, req_id)
            if _txn_seen_or_mark(state, req_id):
                return
            cleaned = {str(k): float(v) for k, v in dict(vals).items()}
            state.pending_param_ops.append(ParamWriteOp(group=grp, values=cleaned))
            return

        case ParamCancel(group=grp, req_id=req_id, session_id=session_id):
            _txn_ack(state, req_id)
            if _txn_seen_or_mark(state, req_id):
                return
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
