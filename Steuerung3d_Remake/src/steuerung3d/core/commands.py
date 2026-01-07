from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union


@dataclass(frozen=True)
class AxisCommand:
    type: Literal["axis_command"] = "axis_command"
    axis_id: str = ""
    enable: bool | None = None
    vel: float | None = None


@dataclass(frozen=True)
class EmergencyStopCommand:
    type: Literal["estop_command"] = "estop_command"
    estop: bool = True


Command = Union[AxisCommand, EmergencyStopCommand]
