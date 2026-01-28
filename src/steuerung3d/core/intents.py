from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Union


# Keep "type" as an explicit discriminant: easy for codecs + pattern matching.
@dataclass(frozen=True)
class EnableAxis:
    type: Literal["enable_axis"] = "enable_axis"
    axis_id: str = ""
    enable: bool = True
    # Optional: the HiP identity sending this command (used for claim enforcement)
    hip_id: str = ""


@dataclass(frozen=True)
class JogAxis:
    type: Literal["jog_axis"] = "jog_axis"
    axis_id: str = ""
    vel: float = 0.0  # units/s (placeholder)
    # Optional: the HiP identity sending this command (used for claim enforcement)
    hip_id: str = ""


@dataclass(frozen=True)
class ClaimAxis:
    """Claim exclusive control of an axis (auto-claimed by HiP on selection)."""
    type: Literal["claim_axis"] = "claim_axis"
    axis_id: str = ""
    hip_id: str = ""
    # Optional correlation
    req_id: str = ""


@dataclass(frozen=True)
class ReleaseAxis:
    """Release a previously claimed axis."""
    type: Literal["release_axis"] = "release_axis"
    axis_id: str = ""
    hip_id: str = ""
    req_id: str = ""


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
    ClaimAxis,
    ReleaseAxis,
    SetEstop,
    RequestEstopReset,  # NEW
    ArmLiveMode,
    DisarmToIdle,
    ClearFault,
    ParamEditBegin,
    ParamWrite,
    ParamCancel,
]
