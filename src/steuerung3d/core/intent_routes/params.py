from __future__ import annotations

from steuerung3d.core.command_frame import ParamCancelOp, ParamEditBeginOp, ParamWriteOp
from steuerung3d.core.intents import ParamCancel, ParamEditBegin, ParamWrite
from steuerung3d.core.intent_handlers.plc_write_keys import PLC_WRITE_KEYS
from steuerung3d.core.intent_handlers.txn import txn_ack as _txn_ack
from steuerung3d.core.intent_handlers.txn import txn_seen_or_mark as _txn_seen_or_mark
from steuerung3d.core.param_registry import normalize_group_values
from steuerung3d.core.state import MachineState
from steuerung3d.core.axis_ids import normalize_axis_id


def handle_param_edit_begin(state: MachineState, intent: ParamEditBegin) -> None:
    req_id = getattr(intent, "req_id", "")
    _txn_ack(state, req_id)
    if _txn_seen_or_mark(state, req_id):
        return

    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    hip_id = str(getattr(intent, "hip_id", "") or "")
    grp = getattr(intent, "group", "")
    op = ParamEditBeginOp(group=grp)

    if axis_id:
        owner = state.claim_owner(axis_id)
        if owner and hip_id and owner != hip_id:
            return
        state.pending_param_ops_by_axis.setdefault(axis_id, []).append(op)
    else:
        state.pending_param_ops.append(op)


def handle_param_write(state: MachineState, intent: ParamWrite) -> None:
    req_id = getattr(intent, "req_id", "")
    _txn_ack(state, req_id)
    if _txn_seen_or_mark(state, req_id):
        return

    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    hip_id = str(getattr(intent, "hip_id", "") or "")
    grp = getattr(intent, "group", "")
    vals = getattr(intent, "values", {})

    cleaned = {str(k): float(v) for k, v in dict(vals).items()}
    cleaned, _warnings = normalize_group_values(str(grp), cleaned)

    state.param_commit_req_id = str(req_id or "")
    state.param_commit_group = str(grp or "")
    state.param_commit_desired = dict(cleaned)
    state.param_commit_start_tick = int(state.tick)
    state.param_commit_status = "pending"
    state.param_commit_unmatched = list(sorted(cleaned.keys()))
    state.param_commit_last_device_tick = -1
    state.param_commit_observed_ticks = 0
    state.param_commit_match_streak = 0

    wire_vals = {k: float(v) for k, v in (state.params or {}).items() if k in PLC_WRITE_KEYS}
    wire_vals.update({k: float(v) for k, v in cleaned.items()})
    op = ParamWriteOp(group=grp, values=wire_vals)

    if axis_id:
        owner = state.claim_owner(axis_id)
        if owner and hip_id and owner != hip_id:
            return
        state.pending_param_ops_by_axis.setdefault(axis_id, []).append(op)
    else:
        state.pending_param_ops.append(op)


def handle_param_cancel(state: MachineState, intent: ParamCancel) -> None:
    req_id = getattr(intent, "req_id", "")
    _txn_ack(state, req_id)
    if _txn_seen_or_mark(state, req_id):
        return

    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    hip_id = str(getattr(intent, "hip_id", "") or "")
    grp = getattr(intent, "group", "")

    if str(getattr(state, "param_commit_status", "idle")) == "pending" and str(
        getattr(state, "param_commit_group", "")
    ) == str(grp):
        state.param_commit_status = "cancelled"
        state.param_commit_unmatched = []

    op = ParamCancelOp(group=grp)

    if axis_id:
        owner = state.claim_owner(axis_id)
        if owner and hip_id and owner != hip_id:
            return
        state.pending_param_ops_by_axis.setdefault(axis_id, []).append(op)
    else:
        state.pending_param_ops.append(op)
