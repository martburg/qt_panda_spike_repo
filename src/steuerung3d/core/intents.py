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
    """Request legacy ReSync pulse for an axis.

    TwinCAT legacy downlink has a ReSync field that is typically pulsed to
    clear latched cut markers and to participate in post-E-Stop recovery.
    """

    type: Literal["resync"] = "resync"
    axis_id: str = ""
    hip_id: str = ""


@dataclass(frozen=True)
class ClearFault:
    type: Literal["clear_fault"] = "clear_fault"


# -------- Joystick / operator motion intents (v0.1) --------


ControlMode = Literal["setup_manual", "sync_live"]


@dataclass(frozen=True)
class SetControlMode:
    """Select a joystick control sub-mode.

    Note: This is distinct from the core safety/machine Mode (IDLE/LIVE/ESTOP).
    It's an operator-side mode that influences how joystick samples are
    interpreted (e.g. manual winch jog vs cartesian jog).
    """

    type: Literal["set_control_mode"] = "set_control_mode"
    mode: ControlMode = "setup_manual"


@dataclass(frozen=True)
class JogWinch:
    """Jog a named winch/axis at a signed rate (units/s).

    In the current architecture, winches are represented as axes, so this intent
    is a semantic alias for JogAxis with axis_id==winch_id.
    """

    type: Literal["jog_winch"] = "jog_winch"
    winch_id: str = ""
    rate: float = 0.0
    hip_id: str = ""


@dataclass(frozen=True)
class JogCartesian:
    """Jog in cartesian space (vx, vy, vz).

    v0.1: the core does not yet contain rig kinematics. If axes named X/Y/Z exist,
    the core may map this intent directly to those axes; otherwise it is ignored.
    """

    type: Literal["jog_cartesian"] = "jog_cartesian"
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    hip_id: str = ""


@dataclass(frozen=True)
class SmoothStop:
    """Request a gentle stop (policy/trajectory layer can interpret this).

    v0.1: implemented as an immediate velocity zero on all enabled axes.
    """

    type: Literal["smooth_stop"] = "smooth_stop"


# -------- Joystick state update (v0.2) --------


@dataclass(frozen=True)
class JoyStateUpdate:
    """Atomic joystick state sample."""

    type: Literal["joy_state_update"] = "joy_state_update"
    deadman: bool = False
    select_hip: bool = False
    soll_speed: float = 0.0


# -------- Parameters (axis-agnostic, v0.1) --------

ParamGroup = Literal["pos", "vel", "filter"]


@dataclass(frozen=True)
class ParamEditBegin:
    """Prime the device to accept parameter writes for a parameter group."""
    type: Literal["param_edit_begin"] = "param_edit_begin"
    axis_id: str = ""
    hip_id: str = ""
    group: ParamGroup = "pos"
    # HIP<->Core transaction correlation (optional)
    req_id: str = ""
    session_id: str = ""


@dataclass(frozen=True)
class ParamWrite:
    """Write one or more parameters (key->float) within a group."""
    type: Literal["param_write"] = "param_write"
    axis_id: str = ""
    hip_id: str = ""
    group: ParamGroup = "pos"
    values: Dict[str, float] = field(default_factory=dict)
    # HIP<->Core transaction correlation (optional)
    req_id: str = ""
    session_id: str = ""


@dataclass(frozen=True)
class ParamCancel:
    """Cancel an in-progress edit session for a parameter group."""
    type: Literal["param_cancel"] = "param_cancel"
    axis_id: str = ""
    hip_id: str = ""
    group: ParamGroup = "pos"
    # HIP<->Core transaction correlation (optional)
    req_id: str = ""
    session_id: str = ""


# -------- LiveTick (UI-originated heartbeat) --------


@dataclass(frozen=True)
class EchoLifeTick:
    """Carry a UI-originated heartbeat value through Core to be mirrored by DenSi.

    Semantics (legacy-compatible): HI-P periodically emits EchoLifeTick values.
    Core stores the last value per axis and includes it in CommandFrame.lifetick_echo.
    DenSi copies it into telemetry and mirrors it back so HI-P can observe continuity.
    """

    type: Literal["echo_lifetick"] = "echo_lifetick"
    axis_id: str = ""
    value: int = 0
    hip_id: str = ""


    
Intent = Union[
    EnableAxis,
    JogAxis,
    JogWinch,
    JogCartesian,
    SetControlMode,
    SmoothStop,
    ClaimAxis,
    ReleaseAxis,
    SetEstop,
    RequestEstopReset,  # NEW
    RequestResync,
    ClearFault,
    ParamEditBegin,
    ParamWrite,
    ParamCancel,
    EchoLifeTick,
    JoyStateUpdate,
    RequestRigLease,
    ReleaseRigLease,
    RequestAxisLease,
    ReleaseAxisLease,
]