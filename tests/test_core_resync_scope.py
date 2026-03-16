from __future__ import annotations

from steuerung3d.core.executor import build_command_frame
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import RequestResync
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.axis_router import AxisRouter
from tests.test_axis_router import _CmdSink, _TelemSink


def test_request_resync_requires_owned_axis_and_stays_axis_scoped() -> None:
    st = MachineState()
    st.set_axis_claim("Anton", "hipA")
    st.set_axis_claim("Debby", "hipB")
    st.ensure_axis("Anton")
    st.ensure_axis("Debby")

    apply_intent(st, RequestResync(axis_id="Anton", hip_id="hipA"))

    frame = build_command_frame(st)
    assert frame.resync is False
    assert frame.resync_by_axis == {"Anton": True}

    anton_out, debby_out = _CmdSink([]), _CmdSink([])
    router = AxisRouter(
        axis_ids=["Anton", "Debby"],
        dev_cmd_out_by_axis={"Anton": anton_out, "Debby": debby_out},
        ui_telem_out_by_axis={"Anton": _TelemSink([]), "Debby": _TelemSink([])},
    )

    sent = router.publish_command_frames(frame)
    assert sent == 2
    assert anton_out.frames[0].resync is True
    assert debby_out.frames[0].resync is False


def test_request_resync_denied_for_wrong_or_missing_owner() -> None:
    st = MachineState()
    st.set_axis_claim("Anton", "hipA")

    apply_intent(st, RequestResync(axis_id="Anton", hip_id="hipB"))
    assert st.resync_req_by_axis == {}

    apply_intent(st, RequestResync(axis_id="Anton", hip_id=""))
    assert st.resync_req_by_axis == {}

    apply_intent(st, RequestResync(axis_id="", hip_id="hipA"))
    assert st.resync_req is False
    assert st.resync_req_by_axis == {}


def test_request_resync_allowed_for_supervisor_without_open_hip() -> None:
    st = MachineState()
    st.ensure_axis("Anton")
    apply_intent(st, RequestResync(axis_id="Anton", hip_id="sup", actor_kind="supervisor"))
    assert st.resync_req_by_axis == {"Anton": True}


def test_request_resync_denied_for_supervisor_when_hip_claims_axis() -> None:
    st = MachineState()
    st.set_axis_claim("Anton", "hipA")
    apply_intent(st, RequestResync(axis_id="Anton", hip_id="sup", actor_kind="supervisor"))
    assert st.resync_req_by_axis == {}


def test_request_resync_allowed_for_supervisor_when_supervisor_holds_lease() -> None:
    st = MachineState()
    st.ensure_axis("Anton")
    st.lease_axis_holders["Anton"] = ["sup"]
    apply_intent(st, RequestResync(axis_id="Anton", hip_id="sup", actor_kind="supervisor"))
    assert st.resync_req_by_axis == {"Anton": True}


def test_request_resync_denied_for_supervisor_when_other_holder_exists() -> None:
    st = MachineState()
    st.ensure_axis("Anton")
    st.lease_axis_holders["Anton"] = ["sup", "hipA"]
    apply_intent(st, RequestResync(axis_id="Anton", hip_id="sup", actor_kind="supervisor"))
    assert st.resync_req_by_axis == {}
