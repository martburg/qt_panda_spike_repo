from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Union


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
class RequestEstopReset:
    type: Literal["estop_reset"] = "estop_reset"


@dataclass(frozen=True)
class ArmLiveMode:
    type: Literal["arm_live_mode"] = "arm_live_mode"


@dataclass(frozen=True)
class DisarmToIdle:
    type: Literal["disarm_to_idle"] = "disarm_to_idle"


@dataclass(frozen=True)
class ClearFault:
    type: Literal["clear_fault"] = "clear_fault"


# -------- Parameters (axis-agnostic, v0.1) --------

ParamGroup = Literal["pos", "vel", "filter"]


@dataclass(frozen=True)
class ParamEditBegin:
    """Prime the device to accept parameter writes for a parameter group."""
    type: Literal["param_edit_begin"] = "param_edit_begin"
    group: ParamGroup = "pos"


@dataclass(frozen=True)
class ParamWrite:
    """Write one or more parameters (key->float) within a group."""
    type: Literal["param_write"] = "param_write"
    group: ParamGroup = "pos"
    values: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ParamCancel:
    """Cancel an in-progress edit session for a parameter group."""
    type: Literal["param_cancel"] = "param_cancel"
    group: ParamGroup = "pos"

    
Intent = Union[
    EnableAxis,
    JogAxis,
    SetEstop,
    RequestEstopReset,  # NEW
    ArmLiveMode,
    DisarmToIdle,
    ClearFault,
    ParamEditBegin,
    ParamWrite,
    ParamCancel,
]
