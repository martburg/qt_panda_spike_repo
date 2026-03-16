from __future__ import annotations

from steuerung3d.core.intent_handlers.lease import axis_lease_holders
from steuerung3d.core.state import MachineState


def axis_reset_allowed(
    state: MachineState, axis_id: str, hip_id: str, actor_kind: str = "hip"
) -> tuple[bool, str]:
    """Policy: who is allowed to request an ESTOP reset pulse for an axis.

    Structural extraction: behavior stays identical to the previous inline
    helper in intent_handler.py.
    """

    axis_id = str(axis_id or "")
    hip_id = str(hip_id or "")
    actor_kind = str(actor_kind or "hip")
    if not axis_id:
        return False, "missing_axis"
    if not hip_id:
        return False, "missing_hip"

    claim_owner = state.claim_owner(axis_id)
    holders = axis_lease_holders(state, axis_id)

    if actor_kind == "supervisor":
        if claim_owner or holders:
            return False, "owned_by_hip"
        return True, "supervisor_unowned"

    if claim_owner and hip_id == claim_owner:
        return True, "claim_owner"

    if hip_id in holders:
        return True, "lease_holder"

    if claim_owner or holders:
        return False, "not_owner"
    return False, "no_owner"
