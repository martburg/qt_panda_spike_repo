from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


def _new_axes() -> List[float]:
    return []


def _new_buttons() -> List[int]:
    return []


@dataclass(frozen=True)
class RawControls:
    """Normalized human input sample.

    Design goals:
      - device-agnostic (gamepad now, WWConsole later)
      - stable over time (axes/buttons semantics are mapped elsewhere)
      - easy to log/replay and send over UDP as JSON

    Conventions:
      - axes are floats, typically normalized to [-1.0, +1.0]
      - buttons are ints 0/1 (or bools), length is device-dependent
      - t_ns is monotonic timestamp in nanoseconds (best-effort)
    """

    type: str = "raw_controls"
    t_ns: int = 0
    src: str = ""  # e.g. "gamepad0", "wwconsole", "replay"
    axes: List[float] = field(default_factory=_new_axes)
    buttons: List[int] = field(default_factory=_new_buttons)
