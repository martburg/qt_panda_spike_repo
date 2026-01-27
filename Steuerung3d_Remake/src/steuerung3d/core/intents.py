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



# -------- Live control modes (rigging vs synchronized) --------

ControlMode = Literal["setup_manual", "sync_live"]


@dataclass(frozen=True)
class SetControlMode:
    type: Literal["set_control_mode"] = "set_control_mode"
    mode: ControlMode = "setup_manual"


# -------- Motion intents (rig space vs direct winch) --------

@dataclass(frozen=True)
class JogCartesian:
    """Cartesian rate command in rig coordinates (m/s)."""
    type: Literal["jog_cartesian"] = "jog_cartesian"
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0


@dataclass(frozen=True)
class JogWinch:
    """Direct rope-length rate command for a specific winch (m/s).

    Sign convention should be documented in rig config; typical:
      +rate = pay out (longer rope), -rate = reel in (shorter rope)
    """
    type: Literal["jog_winch"] = "jog_winch"
    winch_id: str = ""
    rate: float = 0.0


@dataclass(frozen=True)
class SmoothStop:
    """Request a controlled ramp-to-zero stop (operator convenience)."""
    type: Literal["smooth_stop"] = "smooth_stop"

# -------- Parameters (axis-agnostic, v0.1) --------

ParamGroup = Literal["pos", "vel", "filter"]


@dataclass(frozen=True)
class ParamEditBegin:
    """Prime the device to accept parameter writes for a parameter group."""
    type: Literal["param_edit_begin"] = "param_edit_begin"
    group: ParamGroup = "pos"
    # HIP<->Core transaction correlation (optional)
    req_id: str = ""
    session_id: str = ""



@dataclass(frozen=True)
class ParamWrite:
    """Write one or more parameters (key->float) within a group."""
    type: Literal["param_write"] = "param_write"
    group: ParamGroup = "pos"
    values: Dict[str, float] = field(default_factory=dict)
    # HIP<->Core transaction correlation (optional)
    req_id: str = ""
    session_id: str = ""



@dataclass(frozen=True)
class ParamCancel:
    """Cancel an in-progress edit session for a parameter group."""
    type: Literal["param_cancel"] = "param_cancel"
    group: ParamGroup = "pos"
    # HIP<->Core transaction correlation (optional)
    req_id: str = ""
    session_id: str = ""


    
Intent = Union[
    EnableAxis,
    JogAxis,
    JogCartesian,
    JogWinch,
    SetControlMode,
    SmoothStop,
    SetEstop,
    RequestEstopReset,  # NEW
    ArmLiveMode,
    DisarmToIdle,
    ClearFault,
    ParamEditBegin,
    ParamWrite,
    ParamCancel,
]
