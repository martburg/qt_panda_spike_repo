from __future__ import annotations

from enum import Enum


class CoreMode(str, Enum):
    ESTOP = "ESTOP"
    FAULT = "FAULT"
    IDLE = "IDLE"
    ARMED = "ARMED"
    READY = "READY"
    LIVE = "LIVE"


def core_mode_value(value: object) -> str:
    if isinstance(value, CoreMode):
        return value.value
    if isinstance(value, str):
        return value
    return ""
