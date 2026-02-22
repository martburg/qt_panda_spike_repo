from __future__ import annotations

from typing import Optional

from steuerung3d.core.intents import JogWinch
from steuerung3d.core.joy_state import clamp_soll_speed


def map_soll_speed_to_jog_winch(
    *,
    winch_id: str,
    soll_speed: float,
    vel_max: float,
    hip_id: str = "",
) -> Optional[JogWinch]:
    winch_id = str(winch_id or "").strip()
    if not winch_id:
        return None
    speed = clamp_soll_speed(soll_speed)
    try:
        vel_max_mps = float(vel_max)
    except Exception:
        vel_max_mps = 0.0
    if vel_max_mps < 0.0:
        vel_max_mps = 0.0
    rate = float(speed) * vel_max_mps
    return JogWinch(winch_id=winch_id, rate=rate, hip_id=str(hip_id or ""))
