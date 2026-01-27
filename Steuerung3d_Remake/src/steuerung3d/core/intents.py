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


    


# -------- Rig workflow (DenSi pairing + sync + recovery) --------

RigModeName = Literal["DISCOVERY", "SETUP_MANUAL", "ARMED_SYNC", "SYNC_ACTIVE", "SYNC_RECOVER", "FAULT_SYNC"]


@dataclass(frozen=True)
class SetRigMode:
    type: Literal["set_rig_mode"] = "set_rig_mode"
    rig_mode: RigModeName = "DISCOVERY"


@dataclass(frozen=True)
class ClaimDensi:
    type: Literal["claim_densi"] = "claim_densi"
    device_id: str = ""
    hip_id: str = ""
    req_id: str = ""


@dataclass(frozen=True)
class ReleaseDensi:
    type: Literal["release_densi"] = 'release_densi'
    device_id: str = ""
    hip_id: str = ""
    req_id: str = ""


@dataclass(frozen=True)
class SetDensiParticipating:
    type: Literal["set_densi_participating"] = "set_densi_participating"
    device_id: str = ""
    participating: bool = True


@dataclass(frozen=True)
class SetDensiAnchor:
    type: Literal["set_densi_anchor"] = "set_densi_anchor"
    device_id: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass(frozen=True)
class ArmSync:
    type: Literal["arm_sync"] = "arm_sync"


@dataclass(frozen=True)
class EnterSync:
    type: Literal["enter_sync"] = "enter_sync"


@dataclass(frozen=True)
class DisarmToSetup:
    type: Literal["disarm_to_setup"] = "disarm_to_setup"


@dataclass(frozen=True)
class RecoverToLastGood:
    type: Literal["recover_to_last_good"] = "recover_to_last_good"


@dataclass(frozen=True)
class ResyncNow:
    type: Literal["resync_now"] = "resync_now"


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
    SetRigMode,
    ClaimDensi,
    ReleaseDensi,
    SetDensiParticipating,
    SetDensiAnchor,
    ArmSync,
    EnterSync,
    DisarmToSetup,
    RecoverToLastGood,
    ResyncNow,
]
