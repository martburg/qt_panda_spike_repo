from __future__ import annotations

from steuerung3d.util.tick import compute_time_tick


def test_compute_time_tick_first_sample_is_zero() -> None:
    delta, prev = compute_time_tick(None, 100)
    assert delta == 0
    assert prev == 100


def test_compute_time_tick_wraps_16bit_counter() -> None:
    # 16-bit wrap: (5 - 65530) mod 65536 = 11
    delta, prev = compute_time_tick(65530, 5)
    assert delta == 11
    assert prev == 5


def test_compute_time_tick_monotonic_increment() -> None:
    delta, prev = compute_time_tick(1000, 1025)
    assert delta == 25
    assert prev == 1025