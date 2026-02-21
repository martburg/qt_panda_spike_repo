from __future__ import annotations

from steuerung3d.core.executor import build_command_frame
from steuerung3d.core.rig_logic import note_densi_seen
from steuerung3d.core.state import MachineState


def test_stale_device_forces_safe_command_frame() -> None:
    st = MachineState()
    axis_id = "X"

    st.densi_offline_after_ticks = 2
    st.ensure_axis(axis_id)
    cmd = st.ensure_axis_cmd(axis_id)
    cmd.enable = True
    cmd.vel = 1.0
    st.lease_axis_holders[axis_id] = ["hip-a"]

    note_densi_seen(st, axis_id, device_tick=0)

    st.tick = 3
    frame = build_command_frame(st)

    sp = frame.axes[axis_id]
    assert sp.enable is False
    assert sp.vel == 0.0
