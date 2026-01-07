from __future__ import annotations

from dataclasses import dataclass
from time import monotonic_ns


@dataclass(frozen=True)
class Timebase:
    """
    Deterministic core tick timing.
    - dt_s is the *intended* fixed timestep.
    - monotonic timestamps are for diagnostics/logging only.
    """
    dt_s: float

    def now_ns(self) -> int:
        return monotonic_ns()
