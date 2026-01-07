from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class AxisSetpoint:
    enable: bool
    vel: float  # units/s (placeholder)


@dataclass(frozen=True)
class CommandFrame:
    tick: int
    t_s: float
    estop: bool
    fault: bool
    mode: str
    axes: Dict[str, AxisSetpoint]
