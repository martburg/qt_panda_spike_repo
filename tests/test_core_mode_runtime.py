from __future__ import annotations

from steuerung3d.core.mode_aggregate import AggregateInputs, AxisSafetyFacts, aggregate_core_mode
from steuerung3d.core.state import MachineState


def test_aggregate_core_mode_is_pure_and_state_application_is_explicit() -> None:
    st = MachineState()
    default_mode = st.core_mode

    # Aggregation is pure: it must not mutate MachineState.
    result = aggregate_core_mode(
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
    assert st.core_mode == default_mode

    # Application is explicit (the runtime loop / engine owns state mutation).
    st.core_mode = result.core_mode
    st.core_blocked_by = list(result.blocked_by)
    st.core_axis_gate = dict(result.axis_gate)
    st.core_motion_allowed = bool(result.motion_allowed)

    assert st.core_mode == result.core_mode
    assert st.core_blocked_by == list(result.blocked_by)
    assert st.core_axis_gate == dict(result.axis_gate)
