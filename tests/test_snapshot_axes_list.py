from __future__ import annotations

from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot


def test_snapshot_lists_axes_for_ui_population():
    st = MachineState()
    st.ensure_axis("Anton").pos = 1.25
    st.ensure_axis("Debby").pos = -0.5

    snap = TelemetrySnapshot.from_state(st)
    assert set(snap.axes.keys()) == {"Anton", "Debby"}
    assert snap.axes["Anton"].pos == 1.25
