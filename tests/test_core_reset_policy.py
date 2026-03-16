from __future__ import annotations

from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import RequestEstopReset
from steuerung3d.core.state import MachineState


def test_estop_reset_denied_without_axis() -> None:
    st = MachineState()
    apply_intent(st, RequestEstopReset(axis_id="", hip_id="hipA"))
    assert not st.estop_reset_req_by_axis
    assert st.estop_reset_denied_count_by_axis.get("<none>") == 1


def test_estop_reset_denied_without_hip() -> None:
    st = MachineState()
    st.set_axis_claim("X", "hipA")
    apply_intent(st, RequestEstopReset(axis_id="X", hip_id=""))
    assert not st.estop_reset_req_by_axis
    assert st.estop_reset_denied_count_by_axis.get("X") == 1


def test_estop_reset_allowed_for_claim_owner() -> None:
    st = MachineState()
    st.set_axis_claim("X", "hipA")
    apply_intent(st, RequestEstopReset(axis_id="X", hip_id="hipA"))
    assert st.estop_reset_req_by_axis.get("X") is True


def test_estop_reset_allowed_for_lease_holder() -> None:
    st = MachineState()
    st.lease_axis_holders["X"] = ["hipA"]
    apply_intent(st, RequestEstopReset(axis_id="X", hip_id="hipA"))
    assert st.estop_reset_req_by_axis.get("X") is True


def test_estop_reset_denied_for_other_hip() -> None:
    st = MachineState()
    st.set_axis_claim("X", "hipA")
    apply_intent(st, RequestEstopReset(axis_id="X", hip_id="hipB"))
    assert not st.estop_reset_req_by_axis
    assert st.estop_reset_denied_count_by_axis.get("X") == 1


def test_estop_reset_denied_without_owner() -> None:
    st = MachineState()
    apply_intent(st, RequestEstopReset(axis_id="X", hip_id="hipA"))
    assert not st.estop_reset_req_by_axis
    assert st.estop_reset_denied_count_by_axis.get("X") == 1


def test_estop_reset_allowed_for_supervisor_when_axis_unowned() -> None:
    st = MachineState()
    apply_intent(st, RequestEstopReset(axis_id="X", hip_id="sup", actor_kind="supervisor"))
    assert st.estop_reset_req_by_axis.get("X") is True


def test_estop_reset_denied_for_supervisor_when_axis_owned() -> None:
    st = MachineState()
    st.set_axis_claim("X", "hipA")
    apply_intent(st, RequestEstopReset(axis_id="X", hip_id="sup", actor_kind="supervisor"))
    assert not st.estop_reset_req_by_axis
    assert st.estop_reset_denied_count_by_axis.get("X") == 1
