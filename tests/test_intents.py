from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, JogWinch, SetEstop, RequestAxisLease
from steuerung3d.core.executor import build_command_frame
from steuerung3d.core.state import MachineState


def test_enable_and_jog_writes_command_state_only_in_live():
    st = MachineState()
    hip_id = "hipA"
    apply_intent(st, RequestAxisLease(axis_id="X", hip_id=hip_id, req_id="lease-1"))

    # Not LIVE -> ignored
    apply_intent(st, EnableAxis(axis_id="X", enable=True, hip_id=hip_id))
    apply_intent(st, JogAxis(axis_id="X", vel=1.25, hip_id=hip_id))
    assert st.axis_cmd.get("X") is None

    # LIVE -> commands are accepted
    apply_intent(st, ArmLiveMode())
    apply_intent(st, EnableAxis(axis_id="X", enable=True, hip_id=hip_id))
    apply_intent(st, JogAxis(axis_id="X", vel=1.25, hip_id=hip_id))

    cmd = st.axis_cmd["X"]
    assert cmd.enable is True
    assert cmd.vel == 1.25


def test_estop_disables_axes_and_blocks_motion():
    st = MachineState()
    hip_id = "hipA"
    apply_intent(st, RequestAxisLease(axis_id="X", hip_id=hip_id, req_id="lease-2"))
    st.ensure_axis("X").enabled = True
    st.axes["X"].vel = 1.0

    apply_intent(st, SetEstop(estop=True))
    assert st.estop is True
    assert st.axes["X"].enabled is False
    assert st.axes["X"].vel == 0.0

    # motion intents ignored while estopped
    apply_intent(st, EnableAxis(axis_id="X", enable=True, hip_id=hip_id))
    apply_intent(st, JogAxis(axis_id="X", vel=2.0, hip_id=hip_id))

    # command state should still be absent
    assert st.axis_cmd.get("X") is None
    # measured remains clamped
    assert st.axes["X"].enabled is False
    assert st.axes["X"].vel == 0.0


def test_jog_winch_writes_vel_in_command_frame() -> None:
    st = MachineState()
    hip_id = "hipA"
    apply_intent(st, RequestAxisLease(axis_id="Anton", hip_id=hip_id, req_id="lease-3"))
    apply_intent(st, ArmLiveMode())
    apply_intent(st, EnableAxis(axis_id="Anton", enable=True, hip_id=hip_id))
    apply_intent(st, JogWinch(winch_id="Anton", rate=-0.5, hip_id=hip_id))

    cmd = build_command_frame(st)
    assert "Anton" in cmd.axes
    assert cmd.axes["Anton"].vel == -0.5
