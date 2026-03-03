from __future__ import annotations

from steuerung3d.apps.yellow.engines.densi.motion_clamp import (
    apply_estop_clamp_to_state,
    compute_moving_guard,
)
from steuerung3d.core.state import MachineState


def test_compute_moving_guard_velocity_threshold() -> None:
    st = MachineState()
    st.ensure_axis("A")
    st.axes["A"].vel = 0.0
    assert compute_moving_guard(state=st, axis_ids=["A"]) is False

    st.axes["A"].vel = 0.002
    assert compute_moving_guard(state=st, axis_ids=["A"]) is True


def test_apply_estop_clamp_to_state_disables_axes() -> None:
    st = MachineState(estop=True)
    st.ensure_axis("A")
    st.ensure_axis("B")
    st.axes["A"].enabled = True
    st.axes["A"].vel = 1.0
    st.axes["B"].enabled = True
    st.axes["B"].vel = -1.0

    apply_estop_clamp_to_state(state=st)

    assert st.axes["A"].enabled is False
    assert st.axes["A"].vel == 1.0
    assert st.axes["B"].enabled is False
    assert st.axes["B"].vel == -1.0
