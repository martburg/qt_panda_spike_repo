"""Protocol codec.

Encodes/decodes JSON-ish frames between components.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.control_context import ControlContext
from steuerung3d.core.intents import (
    ClaimAxis,
    ClearFault,
    EchoLifeTick,
    EnableAxis,
    Intent,
    JogAxis,
    JogCartesian,
    JogWinch,
    JoyStateUpdate,
    LocalAxisManualRequest,
    ParamCancel,
    ParamEditBegin,
    ParamWrite,
    ReleaseAxis,
    ReleaseAxisLease,
    ReleaseRigLease,
    RequestAxisLease,
    RequestEstopReset,  # NEW
    RequestResync,
    RequestRigLease,
    SetControlMode,
    SetEstop,
    SmoothStop,
)
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.codec_decode_support import (
    decode_command_frame_payload,
    decode_telemetry_payload,
)
from steuerung3d.protocol.raw_controls import RawControls

# ---------------------------
# Intents
# ---------------------------

_INTENT_TYPE_MAP: dict[str, type[Intent]] = {
    "enable_axis": EnableAxis,
    "jog_axis": JogAxis,
    "jog_winch": JogWinch,
    "local_axis_manual": LocalAxisManualRequest,
    "jog_cartesian": JogCartesian,
    "set_control_mode": SetControlMode,
    "smooth_stop": SmoothStop,
    "claim_axis": ClaimAxis,
    "release_axis": ReleaseAxis,
    "request_rig_lease": RequestRigLease,
    "release_rig_lease": ReleaseRigLease,
    "request_axis_lease": RequestAxisLease,
    "release_axis_lease": ReleaseAxisLease,
    "set_estop": SetEstop,
    "estop_reset": RequestEstopReset,  # NEW
    "resync": RequestResync,
    "clear_fault": ClearFault,
    # parameters (axis-agnostic)
    "param_edit_begin": ParamEditBegin,
    "param_write": ParamWrite,
    "param_cancel": ParamCancel,
    "echo_lifetick": EchoLifeTick,
    "joy_state_update": JoyStateUpdate,
}


def register_intent_type(type_name: str, cls: type[Intent]) -> None:
    """Register an intent type for decoding.

    This keeps the existing explicit map (stable + audit-friendly) while
    providing a single extension point for new intents.
    """

    t = str(type_name or "").strip()
    if not t:
        raise ValueError("type_name must be non-empty")
    if t in _INTENT_TYPE_MAP and _INTENT_TYPE_MAP[t] is not cls:
        raise ValueError(f"intent type already registered: {t}")
    _INTENT_TYPE_MAP[t] = cls


def encode_intent(intent: Intent) -> Dict[str, Any]:
    return asdict(intent)


def decode_intent(payload: Dict[str, Any]) -> Intent:
    t = payload.get("type")
    if not isinstance(t, str):
        raise ValueError("intent payload missing 'type'")
    cls: type[Intent] | None = _INTENT_TYPE_MAP.get(t)
    if cls is None:
        raise ValueError(f"unknown intent type: {t}")
    # dataclass ctor matches keys (including 'type')
    return cls(**payload)


# ---------------------------
# Control context
# ---------------------------


def encode_control_context(ctx: ControlContext) -> Dict[str, Any]:
    return asdict(ctx)


def decode_control_context(payload: Dict[str, Any]) -> ControlContext:
    return ControlContext(**payload)


# ---------------------------
# Telemetry
# ---------------------------


def encode_telemetry(snap: TelemetrySnapshot) -> Dict[str, Any]:
    return asdict(snap)


def decode_telemetry(payload: Dict[str, Any]) -> TelemetrySnapshot:
    return decode_telemetry_payload(payload)


# ---------------------------
# RawControls (human input seam)
# ---------------------------


def encode_raw_controls(rc: RawControls) -> Dict[str, Any]:
    return asdict(rc)


def decode_raw_controls(payload: Dict[str, Any]) -> RawControls:
    # keep decoding resilient (older logs / missing keys)
    axes_in = payload.get("axes", [])
    buttons_in = payload.get("buttons", [])
    return RawControls(
        type=str(payload.get("type", "raw_controls")),
        t_ns=int(payload.get("t_ns", 0)),
        src=str(payload.get("src", "")),
        axes=[float(x) for x in list(axes_in)],
        buttons=[int(x) for x in list(buttons_in)],
    )


# ---------------------------
# CommandFrame
# ---------------------------


def encode_command_frame(frame: CommandFrame) -> Dict[str, Any]:
    # Custom encode to keep regression hashes stable when new optional fields
    # are empty (e.g. lifetick_echo).
    d = asdict(frame)
    # omit empty optional keys
    if not d.get("lifetick_echo"):
        d.pop("lifetick_echo", None)
    if not d.get("resync_by_axis"):
        d.pop("resync_by_axis", None)
    if not d.get("main_reset_by_axis"):
        d.pop("main_reset_by_axis", None)
    if not d.get("guider_reset_by_axis"):
        d.pop("guider_reset_by_axis", None)
    # keep hashes stable: omit legacy knobs when at default values
    if d.get("intent", True) is True:
        d.pop("intent", None)
    if not d.get("resync", False):
        d.pop("resync", None)
    if not d.get("gui_not_halt", False):
        d.pop("gui_not_halt", None)
    return d


def decode_command_frame(payload: Dict[str, Any]) -> CommandFrame:
    return decode_command_frame_payload(payload)
