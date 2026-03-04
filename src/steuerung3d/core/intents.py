from __future__ import annotations

"""Core intent types.

This module is intentionally a *barrel* that re-exports intent families from
smaller modules (motion/admin/rig/meta). External import sites remain stable
(`from steuerung3d.core.intents import JogAxis`, etc.).
"""

from typing import Union

from .intents_admin import (
    ClaimAxis,
    ClearFault,
    ReleaseAxis,
    ReleaseAxisLease,
    ReleaseRigLease,
    RequestAxisLease,
    RequestEstopReset,
    RequestGuiderReset,
    RequestMainReset,
    RequestResync,
    RequestRigLease,
    SetEstop,
)
from .intents_meta import EchoLifeTick, JoyStateUpdate
from .intents_motion import (
    ControlMode,
    EnableAxis,
    JogAxis,
    JogCartesian,
    JogWinch,
    SetControlMode,
    SmoothStop,
)
from .intents_rig import ParamCancel, ParamEditBegin, ParamGroup, ParamWrite


Intent = Union[
    # Motion
    EnableAxis,
    JogAxis,
    JogWinch,
    JogCartesian,
    SetControlMode,
    SmoothStop,
    # Ownership / safety
    ClaimAxis,
    ReleaseAxis,
    SetEstop,
    RequestEstopReset,
    RequestResync,
    RequestMainReset,
    RequestGuiderReset,
    ClearFault,
    # Params
    ParamEditBegin,
    ParamWrite,
    ParamCancel,
    # Meta
    EchoLifeTick,
    JoyStateUpdate,
    # Leases
    RequestRigLease,
    ReleaseRigLease,
    RequestAxisLease,
    ReleaseAxisLease,
]


__all__ = [
    # Families
    "ControlMode",
    "ParamGroup",
    "Intent",
    # Motion
    "EnableAxis",
    "JogAxis",
    "JogWinch",
    "JogCartesian",
    "SetControlMode",
    "SmoothStop",
    # Ownership / safety
    "ClaimAxis",
    "ReleaseAxis",
    "SetEstop",
    "RequestEstopReset",
    "RequestResync",
    "RequestMainReset",
    "RequestGuiderReset",
    "ClearFault",
    # Params
    "ParamEditBegin",
    "ParamWrite",
    "ParamCancel",
    # Meta
    "EchoLifeTick",
    "JoyStateUpdate",
    # Leases
    "RequestRigLease",
    "ReleaseRigLease",
    "RequestAxisLease",
    "ReleaseAxisLease",
]
