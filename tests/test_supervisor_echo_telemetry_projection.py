from __future__ import annotations

from steuerung3d.core.state import AxisState, MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot


def test_from_state_projects_lifetick_echo_into_rx_and_diff() -> None:
    st = MachineState(
        axes={"Anton": AxisState(meta={"device_tick": 120})},
        lifetick_echo_by_axis={"Anton": 65},
    )
    snap = TelemetrySnapshot.from_state(st)
    ax = snap.axes["Anton"]
    assert ax.device_tick == 120
    assert ax.lifetick_rx == 65
    assert ax.lifetick_age == ((120 - 65) & 0xFFFF)
