from __future__ import annotations

from dataclasses import dataclass


def clamp_soll_speed(value: float) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    if v < -1.0:
        return -1.0
    if v > 1.0:
        return 1.0
    return v


@dataclass(frozen=True)
class JoyState:
    deadman: bool = False
    select_hip: bool = False
    soll_speed: float = 0.0
