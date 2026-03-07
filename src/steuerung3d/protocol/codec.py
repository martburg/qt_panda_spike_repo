"""Protocol codec.

Encodes/decodes JSON-ish frames between components.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, decode_param_ops
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
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot
from steuerung3d.protocol.raw_controls import RawControls

# ---------------------------
# Intents
# ---------------------------

_INTENT_TYPE_MAP = {
    "enable_axis": EnableAxis,
    "jog_axis": JogAxis,
    "jog_winch": JogWinch,
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
    cls = _INTENT_TYPE_MAP.get(t)
    if cls is None:
        raise ValueError(f"unknown intent type: {t}")
    # dataclass ctor matches keys (including 'type')
    return cls(**payload)


# ---------------------------
# Telemetry
# ---------------------------


def encode_telemetry(snap: TelemetrySnapshot) -> Dict[str, Any]:
    return asdict(snap)


def decode_telemetry(payload: Dict[str, Any]) -> TelemetrySnapshot:
    # Axes
    axes_in = payload.get("axes", {})
    axes_out = {
        str(axis_id): AxisTelemetry(**ax)
        for axis_id, ax in dict(axes_in).items()
        if isinstance(ax, dict)
    }

    # DenSi registry (optional)
    densis_out: Dict[str, DensiTelemetry] = {}
    densis_in = payload.get("densis", {})
    if isinstance(densis_in, dict):
        for dev_id, d in densis_in.items():
            if isinstance(d, dict):
                try:
                    densis_out[str(dev_id)] = DensiTelemetry(**d)
                except Exception:
                    continue

    joy_in = payload.get("joy", {})
    joy = JoyState()
    if isinstance(joy_in, dict):
        selected_axes = tuple(
            str(x) for x in list(joy_in.get("selected_axes", ())) if str(x).strip()
        )
        joy = JoyState(
            deadman=bool(joy_in.get("deadman", False)),
            select_hip=bool(joy_in.get("select_hip", False)) or bool(selected_axes),
            soll_speed=clamp_soll_speed(joy_in.get("soll_speed", 0.0)),
            selected_axes=selected_axes,
        )

    lease_rig = str(payload.get("lease_rig", ""))
    lease_rig_holder = str(payload.get("lease_rig_holder", lease_rig))
    lease_axis_in = payload.get("lease_axis", {})
    lease_axis: Dict[str, list[str]] = {}
    if isinstance(lease_axis_in, dict):
        for k, v in lease_axis_in.items():
            if isinstance(v, (list, tuple)):
                lease_axis[str(k)] = [str(x) for x in list(v)]
    lease_axis_holders_in = payload.get("lease_axis_holders", {})
    lease_axis_holders: Dict[str, list[str]] = {}
    if isinstance(lease_axis_holders_in, dict):
        for k, v in lease_axis_holders_in.items():
            if isinstance(v, (list, tuple)):
                lease_axis_holders[str(k)] = [str(x) for x in list(v)]

    return TelemetrySnapshot(
        tick=int(payload.get("tick", 0)),
        t_s=float(payload.get("t_s", 0.0)),
        core_mode=str(payload.get("core_mode", "")),
        estop=bool(payload.get("estop", False)),
        fault=bool(payload.get("fault", False)),
        axes=axes_out,
        # rig workflow (optional)
        rig_mode=str(payload.get("rig_mode", "DISCOVERY")),
        densis=densis_out,
        lease_rig=lease_rig,
        lease_axis=lease_axis,
        lease_rig_holder=lease_rig_holder,
        lease_axis_holders=lease_axis_holders if lease_axis_holders else dict(lease_axis),
        lease_denial_reason=str(payload.get("lease_denial_reason", "")),
        # NEW
        estop_status_word=int(payload.get("estop_status_word", 0)),
        # parameters (optional)
        param_edit_active=bool(payload.get("param_edit_active", False)),
        param_edit_group=str(payload.get("param_edit_group", "")),
        params={k: float(v) for k, v in dict(payload.get("params", {})).items()},
        plc_uplink_fields={
            str(k): str(v) for k, v in dict(payload.get("plc_uplink_fields", {})).items()
        },
        plc_uplink_tail={
            str(k): str(v) for k, v in dict(payload.get("plc_uplink_tail", {})).items()
        },
        axis_estop_status_word={
            str(k): int(v) for k, v in dict(payload.get("axis_estop_status_word", {})).items()
        },
        axis_param_edit_active={
            str(k): bool(v) for k, v in dict(payload.get("axis_param_edit_active", {})).items()
        },
        axis_param_edit_group={
            str(k): str(v) for k, v in dict(payload.get("axis_param_edit_group", {})).items()
        },
        axis_params={
            str(k): {str(pk): float(pv) for pk, pv in dict(v).items()}
            for k, v in dict(payload.get("axis_params", {})).items()
            if isinstance(v, dict)
        },
        axis_plc_uplink_fields={
            str(k): {str(pk): str(pv) for pk, pv in dict(v).items()}
            for k, v in dict(payload.get("axis_plc_uplink_fields", {})).items()
            if isinstance(v, dict)
        },
        axis_plc_uplink_tail={
            str(k): {str(pk): str(pv) for pk, pv in dict(v).items()}
            for k, v in dict(payload.get("axis_plc_uplink_tail", {})).items()
            if isinstance(v, dict)
        },
        axis_param_commit_req_id={
            str(k): str(v) for k, v in dict(payload.get("axis_param_commit_req_id", {})).items()
        },
        axis_param_commit_group={
            str(k): str(v) for k, v in dict(payload.get("axis_param_commit_group", {})).items()
        },
        axis_param_commit_status={
            str(k): str(v) for k, v in dict(payload.get("axis_param_commit_status", {})).items()
        },
        axis_param_commit_age_ticks={
            str(k): int(v) for k, v in dict(payload.get("axis_param_commit_age_ticks", {})).items()
        },
        axis_param_commit_unmatched={
            str(k): [str(x) for x in list(v)]
            for k, v in dict(payload.get("axis_param_commit_unmatched", {})).items()
            if isinstance(v, (list, tuple))
        },
        core_acks=[str(x) for x in list(payload.get("core_acks", []))],
        # observed param commit status (optional)
        param_commit_req_id=str(payload.get("param_commit_req_id", "")),
        param_commit_group=str(payload.get("param_commit_group", "")),
        param_commit_status=str(payload.get("param_commit_status", "idle")),
        param_commit_age_ticks=int(payload.get("param_commit_age_ticks", 0)),
        param_commit_unmatched=[str(x) for x in list(payload.get("param_commit_unmatched", []))],
        joy=joy,
    )


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
    axes_in = payload["axes"]
    axes_out: Dict[str, AxisSetpoint] = {
        axis_id: AxisSetpoint(**ax) for axis_id, ax in axes_in.items()
    }
    return CommandFrame(
        tick=int(payload["tick"]),
        t_s=float(payload["t_s"]),
        estop=bool(payload["estop"]),
        fault=bool(payload["fault"]),
        core_mode=str(payload.get("core_mode", "")),
        axes=axes_out,
        intent=bool(payload.get("intent", True)),
        resync=bool(payload.get("resync", False)),
        gui_not_halt=bool(payload.get("gui_not_halt", False)),
        estop_reset=bool(payload.get("estop_reset", False)),  # NEW
        param_ops=decode_param_ops(payload.get("param_ops", [])),
        lifetick_echo={k: int(v) for k, v in dict(payload.get("lifetick_echo", {})).items()},
        resync_by_axis={k: bool(v) for k, v in dict(payload.get("resync_by_axis", {})).items()},
        main_reset_by_axis={
            k: bool(v) for k, v in dict(payload.get("main_reset_by_axis", {})).items()
        },
        guider_reset_by_axis={
            k: bool(v) for k, v in dict(payload.get("guider_reset_by_axis", {})).items()
        },
    )
