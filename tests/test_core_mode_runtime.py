from __future__ import annotations

from steuerung3d.core.mode_aggregate import AggregateInputs, AxisSafetyFacts, aggregate_and_store
from steuerung3d.core.state import MachineState


def test_aggregate_and_store_updates_state() -> None:
    st = MachineState()
    result = aggregate_and_store(
        st,
        AggregateInputs(
            axes=[
                AxisSafetyFacts(
                    axis_id="A",
                    in_scope=True,
                    estop_bits={},
                    axis_taster=True,
                    axis_armed=True,
                    axis_ready=True,
                    axis_age_ms=0,
                )
            ],
            stale_after_ms=100,
            joy_deadman=False,
            joy_select_hip=False,
            joy_soll_speed=0.0,
        ),
    )
    assert st.core_mode == result.core_mode
    assert st.core_blocked_by == list(result.blocked_by)
    assert st.core_axis_gate == dict(result.axis_gate)
