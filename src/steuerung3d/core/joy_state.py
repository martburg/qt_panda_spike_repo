from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Tuple

from steuerung3d.core.axis_ids import normalize_axis_id


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


def _coerce_selected_axes(values: Iterable[object] | None) -> Tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in list(values or []):
        axis_id = normalize_axis_id(value)
        if (not axis_id) or (axis_id in seen):
            continue
        seen.add(axis_id)
        out.append(axis_id)
    return tuple(out)


@dataclass(frozen=True)
class JoyState:
    deadman: bool = False
    select_hip: bool = False
    soll_speed: float = 0.0
    selected_axes: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "soll_speed", clamp_soll_speed(self.soll_speed))
        object.__setattr__(self, "selected_axes", _coerce_selected_axes(self.selected_axes))

    def selected_for_axis(self, axis_id: object) -> bool:
        axis_norm = normalize_axis_id(axis_id)
        if not axis_norm:
            return False
        if self.selected_axes:
            return axis_norm in self.selected_axes
        return bool(self.select_hip)
