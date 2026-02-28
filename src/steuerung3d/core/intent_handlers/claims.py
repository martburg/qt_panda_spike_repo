from __future__ import annotations

from steuerung3d.core.state import MachineState


def claim_axis(state: MachineState, axis_id: str, hip_id: str, req_id: str) -> None:
    """Handle ClaimAxis intent (legacy exclusive control)."""
    if not axis_id or not hip_id:
        return
    cur = state.claim_owner(axis_id)
    if cur in ("", hip_id):
        state.set_axis_claim(axis_id, hip_id)
        if req_id:
            state.core_acks.append(req_id)
    else:
        # Deny claim; emit a one-shot ack that the HIP can interpret.
        if req_id:
            state.core_acks.append(f"{req_id}:deny:{cur}")


def release_axis(state: MachineState, axis_id: str, hip_id: str, req_id: str) -> None:
    """Handle ReleaseAxis intent."""
    if not axis_id or not hip_id:
        return
    cur = state.claim_owner(axis_id)
    if cur == hip_id:
        state.clear_axis_claim(axis_id, hip_id=hip_id)
        if req_id:
            state.core_acks.append(req_id)
    else:
        if req_id:
            state.core_acks.append(f"{req_id}:noop")
