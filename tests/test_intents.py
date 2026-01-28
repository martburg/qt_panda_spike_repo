from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop
from steuerung3d.core.state import MachineState


def test_enable_and_jog_writes_command_state_only_in_live():
    st = MachineState()

    # Not LIVE -> ignored
    apply_intent(st, EnableAxis(axis_id="X", enable=True))
    apply_intent(st, JogAxis(axis_id="X", vel=1.25))
    assert st.axis_cmd.get("X") is None

    # LIVE -> commands are accepted
    apply_intent(st, ArmLiveMode())
    apply_intent(st, EnableAxis(axis_id="X", enable=True))
    apply_intent(st, JogAxis(axis_id="X", vel=1.25))

    cmd = st.axis_cmd["X"]
    assert cmd.enable is True
    assert cmd.vel == 1.25


def test_estop_disables_axes_and_blocks_motion():
    st = MachineState()
    st.ensure_axis("X").enabled = True
    st.axes["X"].vel = 1.0

    apply_intent(st, SetEstop(estop=True))
    assert st.estop is True
    assert st.axes["X"].enabled is False
    assert st.axes["X"].vel == 0.0

    # motion intents ignored while estopped
    apply_intent(st, EnableAxis(axis_id="X", enable=True))
    apply_intent(st, JogAxis(axis_id="X", vel=2.0))

    # command state should still be absent
    assert st.axis_cmd.get("X") is None
    # measured remains clamped
    assert st.axes["X"].enabled is False
    assert st.axes["X"].vel == 0.0
