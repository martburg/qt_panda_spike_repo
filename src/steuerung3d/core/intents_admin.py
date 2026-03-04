"""Administrative / safety / ownership intents.

Split out of core/intents.py to reduce merge conflicts and keep intent families
cohesive. The public surface remains re-exported from core/intents.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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
class RequestRigLease:
    """Request exclusive rig/world lease."""

    type: Literal["request_rig_lease"] = "request_rig_lease"
    hip_id: str = ""
    req_id: str = ""


@dataclass(frozen=True)
class ReleaseRigLease:
    """Release rig/world lease."""

    type: Literal["release_rig_lease"] = "release_rig_lease"
    hip_id: str = ""
    req_id: str = ""


@dataclass(frozen=True)
class RequestAxisLease:
    """Request axis lease (set-valued holders per axis)."""

    type: Literal["request_axis_lease"] = "request_axis_lease"
    axis_id: str = ""
    hip_id: str = ""
    req_id: str = ""


@dataclass(frozen=True)
class ReleaseAxisLease:
    """Release axis lease for a holder."""

    type: Literal["release_axis_lease"] = "release_axis_lease"
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
    axis_id: str = ""
    hip_id: str = ""


@dataclass(frozen=True)
class RequestResync:
    """Request legacy ReSync pulse for an axis."""

    type: Literal["resync"] = "resync"
    axis_id: str = ""
    hip_id: str = ""


@dataclass(frozen=True)
class RequestMainReset:
    """Request reset pulse for the *main* amplifier (legacy ControlIN bit6)."""

    type: Literal["main_reset"] = "main_reset"
    axis_id: str = ""
    hip_id: str = ""


@dataclass(frozen=True)
class RequestGuiderReset:
    """Request reset pulse for the *guider* amplifier (legacy GuideControlUI bit2)."""

    type: Literal["guider_reset"] = "guider_reset"
    axis_id: str = ""
    hip_id: str = ""


@dataclass(frozen=True)
class ClearFault:
    type: Literal["clear_fault"] = "clear_fault"
