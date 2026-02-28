from __future__ import annotations

from steuerung3d.core.state import MachineState


def txn_ack(state: MachineState, req_id: str) -> None:
    """Record a one-shot ack for HIP (emitted in telemetry)."""
    if req_id:
        state.core_acks.append(req_id)


def txn_seen_or_mark(state: MachineState, req_id: str, *, max_keep: int = 512) -> bool:
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
