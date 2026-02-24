from steuerung3d.core.intent_handler import apply_intent, enforce_core_mode_actions
from steuerung3d.core.intents import EnableAxis, JogAxis, SetEstop, RequestAxisLease
from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.state import MachineState


def test_motion_intents_blocked_outside_live():
    st = MachineState()
    st.ensure_axis("X")
    hip_id = "hipA"
    apply_intent(st, RequestAxisLease(axis_id="X", hip_id=hip_id, req_id="lease-1"))

    # Outside LIVE: enabling/jogging should do nothing (policy in v0.1)
    st.core_mode = CoreMode.IDLE
    apply_intent(st, EnableAxis(axis_id="X", enable=True, hip_id=hip_id))
    apply_intent(st, JogAxis(axis_id="X", vel=1.0, hip_id=hip_id))
    enforce_core_mode_actions(st)

    assert st.axis_cmd["X"].enable is False
    assert st.axis_cmd["X"].vel == 0.0

    # Mark core LIVE: now they take effect (in command state)
    st.core_mode = CoreMode.LIVE
    apply_intent(st, EnableAxis(axis_id="X", enable=True, hip_id=hip_id))
    apply_intent(st, JogAxis(axis_id="X", vel=1.0, hip_id=hip_id))

    cmd = st.axis_cmd["X"]
    assert cmd.enable is True
    assert cmd.vel == 1.0


def test_estop_forces_disable_and_zero_measured():
    st = MachineState()
    st.ensure_axis("X").enabled = True
    st.axes["X"].vel = 2.0

    apply_intent(st, SetEstop(estop=True))
    assert st.axes["X"].enabled is False
    assert st.axes["X"].vel == 0.0
