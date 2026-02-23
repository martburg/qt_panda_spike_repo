from __future__ import annotations

from steuerung3d.core.mode_aggregate import (
    AggregateInputs,
    AxisSafetyFacts,
    aggregate_core_mode,
)


def _axis(
    axis_id: str,
    *,
    in_scope: bool = True,
    axis_estop: bool | None = False,
    axis_started: bool | None = True,
    axis_fault: bool | None = False,
    axis_taster_enabled: bool | None = True,
    axis_armed: bool | None = True,
    axis_ready: bool | None = True,
    axis_age_ms: int | None = 0,
) -> AxisSafetyFacts:
    return AxisSafetyFacts(
        axis_id=axis_id,
        in_scope=in_scope,
        axis_estop=axis_estop,
        axis_started=axis_started,
        axis_fault=axis_fault,
        axis_taster_enabled=axis_taster_enabled,
        axis_armed=axis_armed,
        axis_ready=axis_ready,
        axis_age_ms=axis_age_ms,
    )


def _codes(result) -> set[str]:
    return {r.code for r in result.blocked_by}


def test_out_of_scope_axis_does_not_block() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[
                _axis("A"),
                _axis("B", in_scope=False, axis_estop=True, axis_age_ms=None),
            ],
            stale_after_ms=100,
            live_request=False,
            joy_deadman=False,
            joy_select=False,
        )
    )
    assert res.core_mode == "READY"
    assert "ESTOP" not in _codes(res)


def test_all_axes_out_of_scope_goes_estop() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[
                _axis("A", in_scope=False, axis_age_ms=None),
                _axis("B", in_scope=False, axis_age_ms=None),
            ],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == "ESTOP"
    assert "MISSING" in _codes(res)


def test_stale_blocks_estop() -> None:
    res = aggregate_core_mode(
        AggregateInputs(axes=[_axis("A", axis_age_ms=150)], stale_after_ms=100)
    )
    assert res.core_mode == "ESTOP"
    assert "STALE" in _codes(res)


def test_stale_overrides_estop_and_fault() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", axis_age_ms=150, axis_estop=True, axis_fault=True)],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == "ESTOP"
    assert "STALE" in _codes(res)
    assert "ESTOP" not in _codes(res)
    assert "FAULT" not in _codes(res)


def test_missing_blocks_estop() -> None:
    res = aggregate_core_mode(
        AggregateInputs(axes=[_axis("A", axis_started=None)], stale_after_ms=100)
    )
    assert res.core_mode == "ESTOP"
    assert "MISSING" in _codes(res)


def test_estop_blocks() -> None:
    res = aggregate_core_mode(
        AggregateInputs(axes=[_axis("A", axis_estop=True)], stale_after_ms=100)
    )
    assert res.core_mode == "ESTOP"
    assert "ESTOP" in _codes(res)


def test_estop_takes_precedence_over_fault() -> None:
    res = aggregate_core_mode(
        AggregateInputs(axes=[_axis("A", axis_estop=True, axis_fault=True)], stale_after_ms=100)
    )
    assert res.core_mode == "ESTOP"
    assert "ESTOP" in _codes(res)
    assert "FAULT" not in _codes(res)


def test_fault_blocks() -> None:
    res = aggregate_core_mode(
        AggregateInputs(axes=[_axis("A", axis_fault=True)], stale_after_ms=100)
    )
    assert res.core_mode == "ESTOP"
    assert "FAULT" in _codes(res)


def test_not_started_goes_idle() -> None:
    res = aggregate_core_mode(
        AggregateInputs(axes=[_axis("A", axis_started=False)], stale_after_ms=100)
    )
    assert res.core_mode == "IDLE"
    assert "NOT_STARTED" in _codes(res)


def test_multi_axis_not_started_keeps_idle() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", axis_started=True), _axis("B", axis_started=False)],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == "IDLE"
    assert "NOT_STARTED" in _codes(res)


def test_taster_enabled_ready_gate() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", axis_taster_enabled=True, axis_ready=False)],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == "ARMED"
    assert "NOT_READY" in _codes(res)


def test_multi_axis_not_ready_stays_armed() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[
                _axis("A", axis_ready=True, axis_taster_enabled=True),
                _axis("B", axis_ready=False, axis_taster_enabled=True),
            ],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == "ARMED"
    assert "NOT_READY" in _codes(res)


def test_taster_disabled_does_not_require_ready() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[
                _axis(
                    "A",
                    axis_taster_enabled=False,
                    axis_ready=False,
                    axis_armed=False,
                )
            ],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == "READY"


def test_live_requires_ready_request_deadman_select() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A")],
            stale_after_ms=100,
            live_request=True,
            joy_deadman=True,
            joy_select=True,
        )
    )
    assert res.core_mode == "LIVE"


def test_live_drops_to_ready_without_deadman() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A")],
            stale_after_ms=100,
            live_request=True,
            joy_deadman=False,
            joy_select=True,
        )
    )
    assert res.core_mode == "READY"
    assert "NO_DEADMAN" in _codes(res)
