from __future__ import annotations

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


def _codes(result) -> set[str]:
    return {r.code for r in result.blocked_by}


def test_ready_to_live_on_deadman() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", estop_bits=_bits())],
            stale_after_ms=100,
            joy_deadman=True,
        )
    )
    assert res.core_mode == CoreMode.LIVE


def test_live_to_ready_when_deadman_released() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", estop_bits=_bits())],
            stale_after_ms=100,
            joy_deadman=False,
        )
    )
    assert res.core_mode == CoreMode.READY


def test_key0_only_aggregation_ignores_key1_faults() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[
                _axis("A", estop_bits=_bits()),
                _axis("B", estop_bits=_bits(schluessel1=True, network=True)),
            ],
            stale_after_ms=100,
            joy_deadman=False,
        )
    )
    assert res.core_mode == CoreMode.READY
    assert res.axis_gate["B"]["hard_estop_active"] is False


def test_no_key0_axes_is_fault() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[
                _axis("A", estop_bits=_bits(schluessel1=True)),
                _axis("B", estop_bits=_bits(schluessel2=True)),
            ],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == CoreMode.FAULT
    assert "NO_KEY0_AXES" in _codes(res)


def test_key_policy_ignores_network_for_key1() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[
                _axis("A", estop_bits=_bits()),
                _axis("B", estop_bits=_bits(schluessel1=True, network=True)),
            ],
            stale_after_ms=100,
        )
    )
    assert res.axis_gate["B"]["hard_estop_active"] is False


def test_key_policy_ignores_guider_and_enc_for_key2() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[
                _axis("A", estop_bits=_bits()),
                _axis("B", estop_bits=_bits(schluessel2=True, guider=True, dcs_ok=False)),
            ],
            stale_after_ms=100,
        )
    )
    assert res.axis_gate["B"]["hard_estop_active"] is False
    assert res.axis_gate["B"]["fault_estop_active"] is False


def test_estop_when_hard_source_active() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", estop_bits=_bits(network=True))],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == CoreMode.ESTOP


def test_fault_when_ok_chain_breaks() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", estop_bits=_bits(kw30_ok=False))],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == CoreMode.FAULT


def test_idle_when_not_all_armed() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", estop_bits=_bits(), axis_armed=False)],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == CoreMode.IDLE


def test_armed_when_not_all_ready() -> None:
    res = aggregate_core_mode(
        AggregateInputs(
            axes=[_axis("A", estop_bits=_bits(), axis_ready=False)],
            stale_after_ms=100,
        )
    )
    assert res.core_mode == CoreMode.ARMED


def test_select_gates_nonzero_motion() -> None:
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
    assert "NO_SELECT" in _codes(res)
