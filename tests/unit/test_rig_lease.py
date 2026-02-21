from __future__ import annotations

from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import RequestRigLease, ReleaseRigLease
from steuerung3d.core.state import MachineState


def test_request_rig_lease_exclusive_and_denial_reason() -> None:
    st = MachineState()

    apply_intent(st, RequestRigLease(hip_id="hip-a", req_id="r1"))
    assert st.lease_rig == "hip-a"
    assert st.lease_last_denial_reason == ""

    apply_intent(st, RequestRigLease(hip_id="hip-b", req_id="r2"))
    assert st.lease_rig == "hip-a"
    assert "rig_held_by:hip-a" in st.lease_last_denial_reason
    assert any("r2:deny:rig_held_by:hip-a" in a for a in st.core_acks)


def test_request_rig_lease_idempotent_req_id() -> None:
    st = MachineState()

    apply_intent(st, RequestRigLease(hip_id="hip-a", req_id="r1"))
    n0 = len(st.core_acks)

    apply_intent(st, RequestRigLease(hip_id="hip-a", req_id="r1"))
    assert len(st.core_acks) == n0
    assert st.lease_rig == "hip-a"


def test_release_rig_lease_behavior() -> None:
    st = MachineState()

    apply_intent(st, RequestRigLease(hip_id="hip-a", req_id="r1"))
    apply_intent(st, ReleaseRigLease(hip_id="hip-b", req_id="r2"))

    assert st.lease_rig == "hip-a"
    assert st.lease_last_denial_reason == "rig_not_held"

    apply_intent(st, ReleaseRigLease(hip_id="hip-a", req_id="r3"))
    assert st.lease_rig == ""
    assert st.lease_last_denial_reason == ""
