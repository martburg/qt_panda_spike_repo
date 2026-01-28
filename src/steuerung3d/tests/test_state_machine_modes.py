from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop
from steuerung3d.core.mode import Mode
from steuerung3d.core.state import MachineState
from steuerung3d.core.state_machine import enforce_mode_actions


def test_idle_to_live_and_back():
    st = MachineState()
    assert st.mode == Mode.IDLE

    apply_intent(st, ArmLiveMode())
    assert st.mode == Mode.LIVE

    apply_intent(st, SetEstop(estop=True))
    assert st.mode == Mode.ESTOP

    apply_intent(st, SetEstop(estop=False))
    assert st.mode == Mode.IDLE


def test_motion_intents_blocked_outside_live():
    st = MachineState()
    st.ensure_axis("X")

    # In IDLE: enabling/jogging should do nothing (policy in v0.1)
    apply_intent(st, EnableAxis(axis_id="X", enable=True))
    apply_intent(st, JogAxis(axis_id="X", vel=1.0))
    enforce_mode_actions(st)

    assert st.mode == Mode.IDLE
    assert st.axis_cmd.get("X") is None

    # Arm LIVE: now they take effect (in command state)
    apply_intent(st, ArmLiveMode())
    apply_intent(st, EnableAxis(axis_id="X", enable=True))
    apply_intent(st, JogAxis(axis_id="X", vel=1.0))

    assert st.mode == Mode.LIVE
    cmd = st.axis_cmd["X"]
    assert cmd.enable is True
    assert cmd.vel == 1.0


def test_estop_forces_disable_and_zero_measured():
    st = MachineState()
    st.ensure_axis("X").enabled = True
    st.axes["X"].vel = 2.0

    apply_intent(st, SetEstop(estop=True))
    assert st.mode == Mode.ESTOP
    assert st.axes["X"].enabled is False
    assert st.axes["X"].vel == 0.0
