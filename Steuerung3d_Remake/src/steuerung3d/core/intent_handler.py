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
    # rig workflow
    SetRigMode,
    ClaimDensi,
    ReleaseDensi,
    SetDensiParticipating,
    SetDensiAnchor,
    ArmSync,
    EnterSync,
    DisarmToSetup,
    RecoverToLastGood,
    ResyncNow,
    Intent,
)
from steuerung3d.core.mode import Mode
from steuerung3d.core.state import MachineState
from steuerung3d.core.command_frame import ParamEditBeginOp, ParamWriteOp, ParamCancelOp
from steuerung3d.core.state_machine import enforce_mode_actions, normalize_mode
from steuerung3d.core.param_registry import normalize_group_values
from steuerung3d.core.rig_types import RigMode
from steuerung3d.core.rig_logic import (
    ensure_densi,
    freeze_config,
    unfreeze_config,
    validate_can_freeze,
    capture_last_good,
    start_recover_to_last_good,
    stop_recover,
)


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



        # --- RIG WORKFLOW (pairing + sync + recovery) ---
        case SetRigMode(rig_mode=rm):
            # Changing rig mode is only allowed while config is not frozen.
            if getattr(state, 'rig_mode', RigMode.DISCOVERY) in (RigMode.ARMED_SYNC, RigMode.SYNC_ACTIVE, RigMode.SYNC_RECOVER, RigMode.FAULT_SYNC):
                return
            try:
                state.rig_mode = RigMode(str(rm))
            except Exception:
                state.rig_mode = RigMode.DISCOVERY
            return

        case ClaimDensi(device_id=dev, hip_id=hip, req_id=req_id):
            _txn_ack(state, req_id)
            if _txn_seen_or_mark(state, req_id):
                return
            # Frozen config: claims/pairings are locked.
            if getattr(state, 'rig_mode', RigMode.DISCOVERY) in (RigMode.ARMED_SYNC, RigMode.SYNC_ACTIVE, RigMode.SYNC_RECOVER, RigMode.FAULT_SYNC):
                return
            if not dev:
                return
            ensure_densi(state, dev)
            d = state.densi_registry[dev]
            if d.claimed_by_hip and d.claimed_by_hip != str(hip):
                return
            d.claimed_by_hip = str(hip or '')
            return

        case ReleaseDensi(device_id=dev, hip_id=hip, req_id=req_id):
            _txn_ack(state, req_id)
            if _txn_seen_or_mark(state, req_id):
                return
            if getattr(state, 'rig_mode', RigMode.DISCOVERY) in (RigMode.ARMED_SYNC, RigMode.SYNC_ACTIVE, RigMode.SYNC_RECOVER, RigMode.FAULT_SYNC):
                return
            if not dev:
                return
            ensure_densi(state, dev)
            d = state.densi_registry[dev]
            if d.claimed_by_hip == str(hip or ''):
                d.claimed_by_hip = ''
            return

        case SetDensiParticipating(device_id=dev, participating=part):
            if getattr(state, 'rig_mode', RigMode.DISCOVERY) in (RigMode.ARMED_SYNC, RigMode.SYNC_ACTIVE, RigMode.SYNC_RECOVER, RigMode.FAULT_SYNC):
                return
            if not dev:
                return
            ensure_densi(state, dev)
            state.densi_registry[dev].participating = bool(part)
            return

        case SetDensiAnchor(device_id=dev, x=x, y=y, z=z):
            if getattr(state, 'rig_mode', RigMode.DISCOVERY) in (RigMode.ARMED_SYNC, RigMode.SYNC_ACTIVE, RigMode.SYNC_RECOVER, RigMode.FAULT_SYNC):
                return
            if not dev:
                return
            ensure_densi(state, dev)
            state.densi_registry[dev].anchor_xyz = (float(x), float(y), float(z))
            return

        case ArmSync():
            ok, why = validate_can_freeze(state)
            if not ok:
                # stash reason for UI (simple string)
                state.axes.setdefault('_rig', state.ensure_axis('_rig')).meta['arm_sync_error'] = why
                return
            freeze_config(state)
            state.rig_mode = RigMode.ARMED_SYNC
            # freeze: command velocities zeroed
            for cmd in state.axis_cmd.values():
                cmd.vel = 0.0
            return

        case EnterSync():
            if getattr(state, 'rig_mode', RigMode.DISCOVERY) != RigMode.ARMED_SYNC:
                return
            if state.estop or state.fault:
                return
            state.rig_mode = RigMode.SYNC_ACTIVE
            capture_last_good(state)
            return

        case DisarmToSetup():
            # exit any frozen/sync workflow back to setup
            state.rig_mode = RigMode.SETUP_MANUAL
            unfreeze_config(state)
            stop_recover(state)
            for cmd in state.axis_cmd.values():
                cmd.vel = 0.0
            return

        case RecoverToLastGood():
            if getattr(state, 'rig_mode', RigMode.DISCOVERY) != RigMode.SYNC_RECOVER:
                return
            if state.estop or state.fault:
                return
            # allow recovery to arm LIVE automatically
            if state.mode == Mode.IDLE:
                state.mode = Mode.LIVE
            start_recover_to_last_good(state)
            return

        case ResyncNow():
            if getattr(state, 'rig_mode', RigMode.DISCOVERY) != RigMode.SYNC_RECOVER:
                return
            if state.estop or state.fault:
                return
            capture_last_good(state)
            stop_recover(state)
            state.rig_mode = RigMode.ARMED_SYNC
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
