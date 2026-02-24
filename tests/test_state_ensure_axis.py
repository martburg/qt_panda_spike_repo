from __future__ import annotations

from steuerung3d.core.state import MachineState


def test_ensure_axis_initializes_state_and_cmd() -> None:
    st = MachineState()
    st.ensure_axis("Anton")

    assert "Anton" in st.axes
    assert "Anton" in st.axis_cmd


def test_ensure_axis_is_idempotent() -> None:
    st = MachineState()
    st.ensure_axis("Anton")
    axis_state = st.axes["Anton"]
    axis_cmd = st.axis_cmd["Anton"]

    st.ensure_axis("Anton")

    assert st.axes["Anton"] is axis_state
    assert st.axis_cmd["Anton"] is axis_cmd


def test_ensure_axis_defaults() -> None:
    st = MachineState()
    st.ensure_axis("Anton")

    cmd = st.axis_cmd["Anton"]
    assert cmd.enable is False
    assert cmd.vel == 0.0
