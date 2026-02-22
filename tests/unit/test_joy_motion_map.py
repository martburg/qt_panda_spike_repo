from __future__ import annotations

from steuerung3d.apps.yellow.domain.joy_motion_map import map_soll_speed_to_jog_winch


def test_map_soll_speed_clamps() -> None:
    it_neg = map_soll_speed_to_jog_winch(winch_id="Anton", soll_speed=-2.0, vel_max=2.0, hip_id="hip")
    it_pos = map_soll_speed_to_jog_winch(winch_id="Anton", soll_speed=2.0, vel_max=2.0, hip_id="hip")
    assert it_neg is not None
    assert it_pos is not None
    assert it_neg.rate == -2.0
    assert it_pos.rate == 2.0


def test_map_soll_speed_preserves_sign() -> None:
    it = map_soll_speed_to_jog_winch(winch_id="Anton", soll_speed=-0.25, vel_max=3.0, hip_id="hip")
    assert it is not None
    assert it.rate < 0
