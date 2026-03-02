from steuerung3d.util.tick import compute_time_tick, tick_delta_16


def test_tick_delta_16_basic():
    assert tick_delta_16(1055, 1000) == 55


def test_tick_delta_16_wrap():
    prev = 0xFFFA  # 65530
    cur = 0x0005  # 5
    assert tick_delta_16(cur, prev) == (cur - prev) & 0xFFFF


def test_compute_time_tick_first_sample_is_zero():
    delta, prev = compute_time_tick(None, 1234)
    assert delta == 0
    assert prev == 1234


def test_compute_time_tick_updates_prev_and_delta():
    delta1, prev1 = compute_time_tick(None, 1000)
    assert delta1 == 0
    assert prev1 == 1000

    delta2, prev2 = compute_time_tick(prev1, 1050)
    assert delta2 == 50
    assert prev2 == 1050


def test_compute_time_tick_wrap_safe():
    delta, prev = compute_time_tick(0xFFFA, 0x0005)
    assert delta == (0x0005 - 0xFFFA) & 0xFFFF
    assert prev == 0x0005
