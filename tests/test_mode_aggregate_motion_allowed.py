from steuerung3d.core.mode_aggregate import (
    AggregateInputs,
    AxisSafetyFacts,
    aggregate_core_mode,
)
from steuerung3d.core.core_mode import CoreMode

def _bits(**updates: bool) -> dict[str, bool]:
    return dict(updates)

def _axis(
    axis_id: str,
    *,
    in_scope: bool = True,
    estop_bits: dict[str, bool] | None = None,
    axis_taster: bool | None = True,
    axis_armed: bool | None = True,
    axis_ready: bool | None = True,
    axis_age_ms: int | None = 0,
) -> AxisSafetyFacts:
    return AxisSafetyFacts(
        axis_id=axis_id,
        in_scope=in_scope,
        estop_bits=estop_bits,
        axis_taster=axis_taster,
        axis_armed=axis_armed,
        axis_ready=axis_ready,
        axis_age_ms=axis_age_ms,
    )

def test_motion_allowed_with_live_and_no_select() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", estop_bits=_bits())],
            stale_after_ms=100,
            joy_deadman=True,
            joy_select=False,
            joy_soll_speed=0.5,
        )
    )
    assert res.core_mode == CoreMode.LIVE
    assert any(r.code == "NO_SELECT" for r in res.blocked_by)
    assert res.motion_allowed is False

def test_motion_allowed_false_when_estop() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", estop_bits=_bits(network=True))],
            stale_after_ms=100,
            joy_deadman=True,
            joy_select=True,
            joy_soll_speed=0.5,
        )
    )
    assert res.core_mode == CoreMode.ESTOP
    assert res.motion_allowed is False

def test_motion_allowed_false_when_not_ready() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", estop_bits=_bits(), axis_ready=False)],
            stale_after_ms=100,
            joy_deadman=True,
            joy_select=True,
            joy_soll_speed=0.5,
        )
    )
    assert res.core_mode == CoreMode.ARMED
    assert res.motion_allowed is False

def test_motion_allowed_false_when_deadman_released() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", estop_bits=_bits())],
            stale_after_ms=100,
            joy_deadman=False,
            joy_select=True,
            joy_soll_speed=0.5,
        )
    )
    assert res.core_mode == CoreMode.READY
    assert res.motion_allowed is False
