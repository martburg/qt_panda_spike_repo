from __future__ import annotations

import logging
log = logging.getLogger("core")

from steuerung3d.core.intents import (
    ArmLiveMode,
    ClearFault,
    DisarmToIdle,
    EnableAxis,
    ClaimAxis,
    ReleaseAxis,
    JogAxis,
    JogWinch,
    JogCartesian,
    SetControlMode,
    SmoothStop,
    SetEstop,
    RequestEstopReset,
    RequestResync,
    ParamEditBegin,
    ParamWrite,
    ParamCancel,
    EchoLifeTick,
    JoyStateUpdate,
    Intent,
)
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed
from steuerung3d.core.mode import Mode
from steuerung3d.core.state import MachineState
from steuerung3d.core.command_frame import ParamEditBeginOp, ParamWriteOp, ParamCancelOp
from steuerung3d.core.state_machine import enforce_mode_actions, normalize_mode
from steuerung3d.core.param_registry import normalize_group_values

# PLC Modus 'w' expects the full parameter set on each write.
# We merge partial UI writes with last-known params to avoid zeroing untouched fields.
_PLC_WRITE_KEYS = {
    'HardMax','UserMax','UserMin','HardMin',
    'VelMax','AccMax','DccMax','MaxAmp',
    'P','I','D','IL','RampForm',
    'Pitch','PosMax','PosMin',
    'PosWin','VelWin','AccMove','VelMaxMot',
}


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

        # --- OPERATOR CONTROL SUB-MODE (non-safety) ---
        case SetControlMode(mode=cmode):
            # v0.1: store if present; higher layers may display it.
            # Keep this decoupled from core safety Mode (IDLE/LIVE/ESTOP).
            setattr(state, "control_mode", str(cmode))
            return

        case SmoothStop():
            # v0.1: immediate zero velocity on all commanded axes.
            for cmd in state.axis_cmd.values():
                cmd.vel = 0.0
            return

        # --- CLAIMS (exclusive control) ---
        case ClaimAxis(axis_id=axis_id, hip_id=hip_id, req_id=req_id):
            if not axis_id or not hip_id:
                return
            cur = state.axis_claims.get(axis_id, "")
            if cur in ("", hip_id):
                state.axis_claims[axis_id] = hip_id
                _txn_ack(state, req_id)
            else:
                # Deny claim; emit a one-shot ack that the HIP can interpret
                if req_id:
                    state.core_acks.append(f"{req_id}:deny:{cur}")
            return

        case ReleaseAxis(axis_id=axis_id, hip_id=hip_id, req_id=req_id):
            if not axis_id or not hip_id:
                return
            cur = state.axis_claims.get(axis_id, "")
            if cur == hip_id:
                state.axis_claims.pop(axis_id, None)
                _txn_ack(state, req_id)
            else:
                if req_id:
                    state.core_acks.append(f"{req_id}:noop")
            return

        # --- UI livetick echo (not safety-critical) ---
        case EchoLifeTick(axis_id=axis_id, value=value, hip_id=_hip_id):
            axis_id = str(axis_id or "")
            if not axis_id:
                return
            # Store as 16-bit like the legacy PLC fields.
            v16 = int(value) & 0xFFFF
            state.lifetick_echo_by_axis[axis_id] = v16
            log.debug("LIFETICK Core rx EchoLifeTick: axis=%s value=%d hip_id=%s", axis_id, v16, str(_hip_id or ""))
            return

        case JoyStateUpdate(deadman=_deadman, select_hip=_select_hip, soll_speed=_soll_speed):
            state.joy = JoyState(
                deadman=bool(_deadman),
                select_hip=bool(_select_hip),
                soll_speed=clamp_soll_speed(float(_soll_speed)),
            )
            return

        # --- SAFETY / GLOBAL REQUESTS ---

        case SetEstop(estop=want_estop):
            # Tests + legacy expectations: SetEstop immediately latches the
            # core-side estop flag and forces the mode normalization path.
            state.estop = bool(want_estop)

            if state.estop:
                # Block motion: disable all axes and clear measured velocity.
                for ax in state.axes.values():
                    ax.enabled = False
                    ax.vel = 0.0
                # Also clear commanded velocities and enables.
                for cmd in state.axis_cmd.values():
                    cmd.enable = False
                    cmd.vel = 0.0

            normalize_mode(state)
            enforce_mode_actions(state)
            return
        case RequestEstopReset(axis_id=axis_id, hip_id=hip_id):
            # Historical name: RequestEstopReset. In v0.1 this acts as per-axis "clear fault / drive reset".
            axis_id = str(axis_id or "")
            hip_id = str(hip_id or "")

            if axis_id:
                owner = state.axis_claims.get(axis_id, "")
                if owner and hip_id and owner != hip_id:
                    return
                if hasattr(state, "estop_reset_req_by_axis"):
                    state.estop_reset_req_by_axis[axis_id] = True
                else:
                    state.estop_reset_req = True
            else:
                # Backward-compat (single-axis): allow global pulse.
                state.estop_reset_req = True

            normalize_mode(state)
            enforce_mode_actions(state)
            return

        case RequestResync(axis_id=axis_id, hip_id=hip_id):
            # Legacy ReSync pulse request.
            axis_id = str(axis_id or "")
            hip_id = str(hip_id or "")

            if axis_id:
                owner = state.axis_claims.get(axis_id, "")
                if owner and hip_id and owner != hip_id:
                    return
                if hasattr(state, "resync_req_by_axis"):
                    state.resync_req_by_axis[axis_id] = True
                else:
                    state.resync_req = True
            else:
                # Backward-compat (single-axis): allow global pulse.
                state.resync_req = True
            return

        case ParamEditBegin(axis_id=axis_id, hip_id=hip_id, group=grp, req_id=req_id, session_id=session_id):
            _txn_ack(state, req_id)
            if _txn_seen_or_mark(state, req_id):
                return

            axis_id = str(axis_id or "")
            hip_id = str(hip_id or "")
            op = ParamEditBeginOp(group=grp)

            if axis_id and hasattr(state, "pending_param_ops_by_axis"):
                owner = state.axis_claims.get(axis_id, "")
                if owner and hip_id and owner != hip_id:
                    return
                state.pending_param_ops_by_axis.setdefault(axis_id, []).append(op)
            else:
                state.pending_param_ops.append(op)
            return

        case ParamWrite(axis_id=axis_id, hip_id=hip_id, group=grp, values=vals, req_id=req_id, session_id=session_id):
            _txn_ack(state, req_id)
            if _txn_seen_or_mark(state, req_id):
                return

            axis_id = str(axis_id or "")
            hip_id = str(hip_id or "")

            cleaned = {str(k): float(v) for k, v in dict(vals).items()}
            cleaned, _warnings = normalize_group_values(str(grp), cleaned)

            # Begin an "observed" commit: we cannot rely on PLC ACKs, so we
            # consider the write applied once telemetry.params matches these values.
            state.param_commit_req_id = str(req_id or "")
            state.param_commit_group = str(grp or "")
            state.param_commit_desired = dict(cleaned)
            state.param_commit_start_tick = int(state.tick)
            state.param_commit_status = "pending"
            state.param_commit_unmatched = list(sorted(cleaned.keys()))
            state.param_commit_last_device_tick = -1
            state.param_commit_observed_ticks = 0
            state.param_commit_match_streak = 0

            # Merge with last-known params so PLC 'w' writes are full-snapshot.
            wire_vals = {k: float(v) for k, v in (state.params or {}).items() if k in _PLC_WRITE_KEYS}
            wire_vals.update({k: float(v) for k, v in cleaned.items()})
            op = ParamWriteOp(group=grp, values=wire_vals)

            if axis_id and hasattr(state, "pending_param_ops_by_axis"):
                owner = state.axis_claims.get(axis_id, "")
                if owner and hip_id and owner != hip_id:
                    return
                state.pending_param_ops_by_axis.setdefault(axis_id, []).append(op)
            else:
                state.pending_param_ops.append(op)
            return

        case ParamCancel(axis_id=axis_id, hip_id=hip_id, group=grp, req_id=req_id, session_id=session_id):
            _txn_ack(state, req_id)
            if _txn_seen_or_mark(state, req_id):
                return

            axis_id = str(axis_id or "")
            hip_id = str(hip_id or "")

            # Cancel pending observed commit for this group (if any)
            if str(getattr(state, "param_commit_status", "idle")) == "pending" and str(
                getattr(state, "param_commit_group", "")
            ) == str(grp):
                state.param_commit_status = "cancelled"
                state.param_commit_unmatched = []

            op = ParamCancelOp(group=grp)

            if axis_id and hasattr(state, "pending_param_ops_by_axis"):
                owner = state.axis_claims.get(axis_id, "")
                if owner and hip_id and owner != hip_id:
                    return
                state.pending_param_ops_by_axis.setdefault(axis_id, []).append(op)
            else:
                state.pending_param_ops.append(op)
            return
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
        case EnableAxis(axis_id=axis_id, enable=enable, hip_id=hip_id):
            state.ensure_axis(axis_id)
            claim = state.axis_claims.get(axis_id, "")
            if claim and hip_id and claim != hip_id:
                return
            if claim and not hip_id:
                # Backward-compat: if a claim exists and the intent lacks hip_id, ignore.
                return
            cmd = state.ensure_axis_cmd(axis_id)
            cmd.enable = bool(enable)
            if not cmd.enable:
                cmd.vel = 0.0
            return

        case JogAxis(axis_id=axis_id, vel=vel, hip_id=hip_id):
            state.ensure_axis(axis_id)
            claim = state.axis_claims.get(axis_id, "")
            if claim and hip_id and claim != hip_id:
                return
            if claim and not hip_id:
                return
            cmd = state.ensure_axis_cmd(axis_id)
            if cmd.enable:
                cmd.vel = float(vel)
            return

        case JogWinch(winch_id=winch_id, rate=rate, hip_id=hip_id):
            # Semantic alias: winches are axes at this layer.
            axis_id = str(winch_id)
            state.ensure_axis(axis_id)
            claim = state.axis_claims.get(axis_id, "")
            if claim and hip_id and claim != hip_id:
                return
            if claim and not hip_id:
                return
            cmd = state.ensure_axis_cmd(axis_id)
            if cmd.enable:
                cmd.vel = float(rate)
            return

        case JogCartesian(vx=vx, vy=vy, vz=vz, hip_id=hip_id):
            # v0.1: if the system has axes named X/Y/Z, map directly to JogAxis.
            # Otherwise ignore (kinematics layer not implemented yet).
            for axis_id, vel in (("X", vx), ("Y", vy), ("Z", vz)):
                if axis_id in state.axes or axis_id in state.axis_cmd:
                    claim = state.axis_claims.get(axis_id, "")
                    if claim and hip_id and claim != hip_id:
                        continue
                    if claim and not hip_id:
                        continue
                    cmd = state.ensure_axis_cmd(axis_id)
                    if cmd.enable:
                        cmd.vel = float(vel)
            return

        case _:
            return