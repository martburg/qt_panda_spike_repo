from __future__ import annotations

import logging
log = logging.getLogger("core")

from steuerung3d.core.intents import (
    ClearFault,
    EnableAxis,
    ClaimAxis,
    ReleaseAxis,
    RequestRigLease,
    ReleaseRigLease,
    RequestAxisLease,
    ReleaseAxisLease,
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
from steuerung3d.core.core_mode import CoreMode, core_mode_value
from steuerung3d.core.state import MachineState
from steuerung3d.core.command_frame import ParamEditBeginOp, ParamWriteOp, ParamCancelOp
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


def _set_lease_denial(state: MachineState, reason: str, req_id: str = "") -> None:
    state.lease_last_denial_reason = str(reason or "")
    if req_id:
        state.core_acks.append(f"{req_id}:deny:{reason}")


def _axis_lease_holders(state: MachineState, axis_id: str) -> list[str]:
    holders = getattr(state, "lease_axis_holders", {}) or {}
    vals = holders.get(axis_id, []) if isinstance(holders, dict) else []
    if not isinstance(vals, (list, tuple)):
        return []
    return [str(x) for x in list(vals) if str(x)]


def _axis_lease_allows(state: MachineState, axis_id: str, hip_id: str) -> bool:
    """Return whether *hip_id* may send control intents for *axis_id*.

    We support two related concepts:
      1) **lease holders** (future / multi-HiP arbitration)
      2) **claim owner** (legacy behaviour; a DenSi locks to one controlling HiP)

    Some profiles currently set the claim but do not populate lease holders.
    Without this fallback, *all* EnableAxis/JogWinch intents are rejected, so
    cmd_en/cmd_vel stay at zero even though the joystick is active.
    """

    hip_id = str(hip_id or "")
    holders = _axis_lease_holders(state, axis_id)
    if holders and hip_id in holders:
        return True

    # Fallback to legacy claim owner if present.
    #
    # NOTE: MachineState.axis_claims is a Dict[str, str] (axis_id -> hip_id).
    # Some earlier prototypes briefly used a richer claim object; keep a
    # defensive branch so we don't regress if that ever returns.
    claims = getattr(state, "axis_claims", {}) or {}
    claim = claims.get(str(axis_id or "")) if isinstance(claims, dict) else None
    if not claim:
        return False
    if isinstance(claim, str):
        return claim == hip_id
    return str(getattr(claim, "hip_id", "")) == hip_id


def _axis_reset_allowed(state: MachineState, axis_id: str, hip_id: str) -> tuple[bool, str]:
    axis_id = str(axis_id or "")
    hip_id = str(hip_id or "")
    if not axis_id:
        return False, "missing_axis"
    if not hip_id:
        return False, "missing_hip"
    claim_owner = str(state.axis_claims.get(axis_id, "") or "")
    if claim_owner and hip_id == claim_owner:
        return True, "claim_owner"
    holders = _axis_lease_holders(state, axis_id)
    if hip_id in holders:
        return True, "lease_holder"
    if claim_owner or holders:
        return False, "not_owner"
    return False, "no_owner"


def enforce_core_mode_actions(state: MachineState) -> None:
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

        # --- LEASES (rig + axis) ---
        case RequestRigLease(hip_id=hip_id, req_id=req_id):
            if _txn_seen_or_mark(state, req_id):
                return
            hip_id = str(hip_id or "")
            if not hip_id:
                return
            cur = str(getattr(state, "lease_rig", "") or "")
            if cur in ("", hip_id):
                state.lease_rig = hip_id
                state.lease_last_denial_reason = ""
                _txn_ack(state, req_id)
            else:
                _set_lease_denial(state, f"rig_held_by:{cur}", req_id=req_id)
            return

        case ReleaseRigLease(hip_id=hip_id, req_id=req_id):
            if _txn_seen_or_mark(state, req_id):
                return
            hip_id = str(hip_id or "")
            cur = str(getattr(state, "lease_rig", "") or "")
            if hip_id and cur == hip_id:
                state.lease_rig = ""
                state.lease_last_denial_reason = ""
                _txn_ack(state, req_id)
            else:
                _set_lease_denial(state, "rig_not_held", req_id=req_id)
            return

        case RequestAxisLease(axis_id=axis_id, hip_id=hip_id, req_id=req_id):
            if _txn_seen_or_mark(state, req_id):
                return
            axis_id = str(axis_id or "")
            hip_id = str(hip_id or "")
            if not axis_id or not hip_id:
                return
            holders = _axis_lease_holders(state, axis_id)
            if holders and hip_id not in holders:
                _set_lease_denial(state, f"axis_held_by:{','.join(holders)}", req_id=req_id)
                return
            holders = list(dict.fromkeys(holders + [hip_id]))
            if not hasattr(state, "lease_axis_holders"):
                state.lease_axis_holders = {}
            state.lease_axis_holders[axis_id] = holders
            state.lease_last_denial_reason = ""
            _txn_ack(state, req_id)
            return

        case ReleaseAxisLease(axis_id=axis_id, hip_id=hip_id, req_id=req_id):
            if _txn_seen_or_mark(state, req_id):
                return
            axis_id = str(axis_id or "")
            hip_id = str(hip_id or "")
            if not axis_id or not hip_id:
                return
            holders = _axis_lease_holders(state, axis_id)
            if hip_id not in holders:
                _set_lease_denial(state, "axis_not_held", req_id=req_id)
                return
            holders = [h for h in holders if h != hip_id]
            if not hasattr(state, "lease_axis_holders"):
                state.lease_axis_holders = {}
            if holders:
                state.lease_axis_holders[axis_id] = holders
            else:
                state.lease_axis_holders.pop(axis_id, None)
            state.lease_last_denial_reason = ""
            _txn_ack(state, req_id)
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

            enforce_core_mode_actions(state)
            return
        case RequestEstopReset(axis_id=axis_id, hip_id=hip_id):
            # Historical name: RequestEstopReset. In v0.1 this acts as per-axis "clear fault / drive reset".
            axis_id = str(axis_id or "")
            hip_id = str(hip_id or "")

            allowed, _reason = _axis_reset_allowed(state, axis_id, hip_id)
            if not allowed:
                key = axis_id or "<none>"
                state.estop_reset_denied_count_by_axis[key] = int(
                    state.estop_reset_denied_count_by_axis.get(key, 0)
                ) + 1
                return

            if axis_id:
                state.estop_reset_req_by_axis[axis_id] = True
            else:
                key = axis_id or "<none>"
                state.estop_reset_denied_count_by_axis[key] = int(
                    state.estop_reset_denied_count_by_axis.get(key, 0)
                ) + 1
                return

            enforce_core_mode_actions(state)
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
        # fallthrough to mode-gated below
        case _:
            pass

    # --- MODE-GATED INTENTS (LIVE only) ---
    core_mode = core_mode_value(getattr(state, "core_mode", "")).upper()
    if core_mode:
        is_live = core_mode == CoreMode.LIVE.value

    if not is_live:
        enforce_core_mode_actions(state)
        return
    if state.estop or state.fault:
        enforce_core_mode_actions(state)
        return

    match intent:
        case EnableAxis(axis_id=axis_id, enable=enable, hip_id=hip_id):
            state.ensure_axis(axis_id)
            if not _axis_lease_allows(state, axis_id, hip_id):
                state.lease_last_denial_reason = f"axis_lease_required:{axis_id}"
                return
            claim = state.axis_claims.get(axis_id, "")
            if claim and hip_id and claim != hip_id:
                return
            if claim and not hip_id:
                # Backward-compat: if a claim exists and the intent lacks hip_id, ignore.
                return
            cmd = state.axis_cmd[axis_id]  # ensured by ensure_axis() above
            cmd.enable = bool(enable)
            if not cmd.enable:
                cmd.vel = 0.0
            return

        case JogAxis(axis_id=axis_id, vel=vel, hip_id=hip_id):
            state.ensure_axis(axis_id)
            if not _axis_lease_allows(state, axis_id, hip_id):
                state.lease_last_denial_reason = f"axis_lease_required:{axis_id}"
                return
            claim = state.axis_claims.get(axis_id, "")
            if claim and hip_id and claim != hip_id:
                return
            if claim and not hip_id:
                return
            cmd = state.axis_cmd[axis_id]  # ensured by ensure_axis() above
            if cmd.enable:
                cmd.vel = float(vel)
            return

        case JogWinch(winch_id=winch_id, rate=rate, hip_id=hip_id):
            # Semantic alias: winches are axes at this layer.
            axis_id = str(winch_id)
            state.ensure_axis(axis_id)
            if not _axis_lease_allows(state, axis_id, hip_id):
                state.lease_last_denial_reason = f"axis_lease_required:{axis_id}"
                return
            claim = state.axis_claims.get(axis_id, "")
            if claim and hip_id and claim != hip_id:
                return
            if claim and not hip_id:
                return
            cmd = state.axis_cmd[axis_id]  # ensured by ensure_axis() above
            if cmd.enable:
                cmd.vel = float(rate)
            return

        case JogCartesian(vx=vx, vy=vy, vz=vz, hip_id=hip_id):
            # v0.1: if the system has axes named X/Y/Z, map directly to JogAxis.
            # Otherwise ignore (kinematics layer not implemented yet).
            lease_rig = str(getattr(state, "lease_rig", "") or "")
            if not lease_rig or (hip_id and lease_rig != hip_id):
                state.lease_last_denial_reason = "rig_lease_required"
                return
            for axis_id, vel in (("X", vx), ("Y", vy), ("Z", vz)):
                if axis_id in state.axes or axis_id in state.axis_cmd:
                    if not _axis_lease_allows(state, axis_id, hip_id):
                        state.lease_last_denial_reason = f"axis_lease_required:{axis_id}"
                        continue
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