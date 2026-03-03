from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol, Tuple


@dataclass(frozen=True)
class CartesianCommand:
    """World-frame cartesian command.

    v0: velocity-driven, with optional position target once available.
    """

    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0

    # Optional position target (world frame), for actuators that use position + velocity.
    x: float | None = None
    y: float | None = None
    z: float | None = None


@dataclass(frozen=True)
class AxisCommand:
    """Per-axis command produced by kinematics."""

    pos: float
    vel: float


class RigKinematics(Protocol):
    """Kinematics mapping: n-DOF cartesian -> n-DOF axis commands."""

    def cartesian_to_axes(
        self,
        *,
        participating: Tuple[str, ...],
        anchors: Dict[str, Tuple[float, float, float]],
        cmd: CartesianCommand,
    ) -> Dict[str, AxisCommand]: ...
