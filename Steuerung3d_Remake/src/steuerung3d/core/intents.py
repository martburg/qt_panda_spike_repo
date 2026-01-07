from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union


# Keep "type" as an explicit discriminant: easy for codecs + pattern matching.
@dataclass(frozen=True)
class EnableAxis:
    type: Literal["enable_axis"] = "enable_axis"
    axis_id: str = ""
    enable: bool = True


@dataclass(frozen=True)
class JogAxis:
    type: Literal["jog_axis"] = "jog_axis"
    axis_id: str = ""
    vel: float = 0.0  # units/s (placeholder)


@dataclass(frozen=True)
class SetEstop:
    type: Literal["set_estop"] = "set_estop"
    estop: bool = True

@dataclass(frozen=True)
class ArmLiveMode:
    type: Literal["arm_live_mode"] = "arm_live_mode"


@dataclass(frozen=True)
class DisarmToIdle:
    type: Literal["disarm_to_idle"] = "disarm_to_idle"


@dataclass(frozen=True)
class ClearFault:
    type: Literal["clear_fault"] = "clear_fault"

    
Intent = Union[EnableAxis, JogAxis, SetEstop, ArmLiveMode, DisarmToIdle, ClearFault]
