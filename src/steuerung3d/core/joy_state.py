from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


def clamp_norm(value: float) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    if v > 1.0:
        return 1.0
    if v < -1.0:
        return -1.0
    return v


def clamp_soll_speed(value: float) -> float:
    return clamp_norm(value)


def canonicalize_selected_axes(selected_axes: Iterable[str] | None) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    if not selected_axes:
        return ()
    for raw in selected_axes:
        axis = str(raw or "").strip()
        if not axis or axis in seen:
            continue
        seen.add(axis)
        out.append(axis)
    return tuple(out)


@dataclass(frozen=True)
class JoyState:
    deadman: bool = False
    select_hip: bool = False
    soll_speed: float = 0.0
    look_pan: float = 0.0
    look_tilt: float = 0.0
    selected_axes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "deadman", bool(self.deadman))
        object.__setattr__(self, "soll_speed", clamp_soll_speed(self.soll_speed))
        object.__setattr__(self, "look_pan", clamp_norm(self.look_pan))
        object.__setattr__(self, "look_tilt", clamp_norm(self.look_tilt))
        selected_axes = canonicalize_selected_axes(self.selected_axes)
        object.__setattr__(self, "selected_axes", selected_axes)
        # Deprecated compatibility mirror only: selection authority is selected_axes.
        object.__setattr__(self, "select_hip", bool(selected_axes))
