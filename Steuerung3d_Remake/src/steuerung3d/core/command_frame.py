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
    estop: bool          # legacy/unused for authority (keep for now)
    fault: bool
    mode: str
    axes: Dict[str, AxisSetpoint]
    estop_reset: bool    # NEW: momentary request to clear device latch
