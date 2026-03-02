from __future__ import annotations

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.intent_handlers.lease import (
    axis_lease_holders as _axis_lease_holders,
    set_lease_denial as _set_lease_denial,
)
from steuerung3d.core.intent_handlers.txn import (
    txn_ack as _txn_ack,
    txn_seen_or_mark as _txn_seen_or_mark,
)
from steuerung3d.core.intents import (
    ReleaseAxisLease,
    ReleaseRigLease,
    RequestAxisLease,
    RequestRigLease,
)
from steuerung3d.core.state import MachineState


def handle_request_rig_lease(state: MachineState, intent: RequestRigLease) -> None:
    req_id = getattr(intent, "req_id", "")
    if _txn_seen_or_mark(state, req_id):
        return
    hip_id = str(getattr(intent, "hip_id", "") or "")
    if not hip_id:
        return
    cur = str(getattr(state, "lease_rig", "") or "")
    if cur in ("", hip_id):
        state.lease_rig = hip_id
        state.lease_last_denial_reason = ""
        _txn_ack(state, req_id)
    else:
        _set_lease_denial(state, f"rig_held_by:{cur}", req_id=req_id)


def handle_release_rig_lease(state: MachineState, intent: ReleaseRigLease) -> None:
    req_id = getattr(intent, "req_id", "")
    if _txn_seen_or_mark(state, req_id):
        return
    hip_id = str(getattr(intent, "hip_id", "") or "")
    cur = str(getattr(state, "lease_rig", "") or "")
    if hip_id and cur == hip_id:
        state.lease_rig = ""
        state.lease_last_denial_reason = ""
        _txn_ack(state, req_id)
    else:
        _set_lease_denial(state, "rig_not_held", req_id=req_id)


def handle_request_axis_lease(state: MachineState, intent: RequestAxisLease) -> None:
    req_id = getattr(intent, "req_id", "")
    if _txn_seen_or_mark(state, req_id):
        return
    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    hip_id = str(getattr(intent, "hip_id", "") or "")
    if not axis_id or not hip_id:
        return
    holders = _axis_lease_holders(state, axis_id)
    if holders and hip_id not in holders:
        _set_lease_denial(state, f"axis_held_by:{','.join(holders)}", req_id=req_id)
        return
    holders = list(dict.fromkeys(holders + [hip_id]))
    state.lease_axis_holders[axis_id] = holders
    state.lease_last_denial_reason = ""
    _txn_ack(state, req_id)


def handle_release_axis_lease(state: MachineState, intent: ReleaseAxisLease) -> None:
    req_id = getattr(intent, "req_id", "")
    if _txn_seen_or_mark(state, req_id):
        return
    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    hip_id = str(getattr(intent, "hip_id", "") or "")
    if not axis_id or not hip_id:
        return
    holders = _axis_lease_holders(state, axis_id)
    if hip_id not in holders:
        _set_lease_denial(state, "axis_not_held", req_id=req_id)
        return
    holders = [h for h in holders if h != hip_id]
    if holders:
        state.lease_axis_holders[axis_id] = holders
    else:
        state.lease_axis_holders.pop(axis_id, None)
    state.lease_last_denial_reason = ""
    _txn_ack(state, req_id)
