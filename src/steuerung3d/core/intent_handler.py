from __future__ import annotations

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
    ParamEditBegin,
    ParamWrite,
    ParamCancel,
    Intent,
)
from steuerung3d.core.mode import Mode
from steuerung3d.core.state import MachineState
from steuerung3d.core.command_frame import ParamEditBeginOp, ParamWriteOp, ParamCancelOp
from steuerung3d.core.state_machine import enforce_mode_actions, normalize_mode
from steuerung3d.core.param_registry import normalize_group_values


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

            state.pending_param_ops.append(ParamWriteOp(group=grp, values=cleaned))
            return

        case ParamCancel(group=grp, req_id=req_id, session_id=session_id):
            _txn_ack(state, req_id)
            if _txn_seen_or_mark(state, req_id):
                return

            # Cancel pending observed commit for this group (if any)
            if str(getattr(state, "param_commit_status", "idle")) == "pending" and str(
                getattr(state, "param_commit_group", "")
            ) == str(grp):
                state.param_commit_status = "cancelled"
                state.param_commit_unmatched = []

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
