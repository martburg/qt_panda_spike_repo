from __future__ import annotations

from steuerung3d.common.staleness import age_ticks, is_stale


def test_age_ticks_none() -> None:
    assert age_ticks(10, None) is None


def test_is_stale_with_none_last_tick() -> None:
    assert is_stale(10, None, 5)


def test_is_stale_boundary_inclusive() -> None:
    assert is_stale(10, 5, 5)
    assert not is_stale(9, 5, 5)


def test_is_stale_large_gap() -> None:
    assert is_stale(1000, 0, 100)
