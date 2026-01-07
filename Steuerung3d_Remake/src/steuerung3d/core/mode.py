from __future__ import annotations

from enum import Enum


class Mode(str, Enum):
    ESTOP = "ESTOP"
    FAULT = "FAULT"
    IDLE = "IDLE"
    LIVE = "LIVE"
