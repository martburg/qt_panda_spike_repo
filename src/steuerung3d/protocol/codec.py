"""Protocol codec.

Encodes/decodes JSON-ish frames between components.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, decode_param_ops
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
    RequestEstopReset,
    RequestResync,
    RequestRigLease,
    SetControlMode,
    SetEstop,
    SmoothStop,
)
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot
from steuerung3d.protocol.raw_controls import RawControls

_INTENT_TYPE_MAP = {
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
    "estop_reset": RequestEstopReset,
    "resync": RequestResync,
    "clear_fault": ClearFault,
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
    return cls(**payload)


def encode_control_context(ctx: ControlContext) -> Dict[str, Any]:
    return asdict(ctx)


def decode_control_context(payload: Dict[str, Any]) -> ControlContext:
    return ControlContext(**payload)


def encode_telemetry(snap: TelemetrySnapshot) -> Dict[str, Any]:
    return asdict(snap)


def _decode_axes(axes_in: object) -> Dict[str, AxisTelemetry]:
    return {
        str(axis_id): AxisTelemetry(**ax)
        for axis_id, ax in dict(axes_in or {}).items()
        if isinstance(ax, dict)
    }


def _decode_densis(densis_in: object) -> Dict[str, DensiTelemetry]:
    densis_out: Dict[str, DensiTelemetry] = {}
    if isinstance(densis_in, dict):
        for dev_id, d in densis_in.items():
            if isinstance(d, dict):
                try:
                    densis_out[str(dev_id)] = DensiTelemetry(**d)
                except Exception:
                    continue
    return densis_out


def _decode_joy_state(joy_in: object) -> JoyState:
    joy = JoyState()
    if isinstance(joy_in, dict):
        selected_axes = tuple(
            str(x) for x in list(joy_in.get("selected_axes", ())) if str(x).strip()
        )
        joy = JoyState(
            deadman=bool(joy_in.get("deadman", False)),
            soll_speed=clamp_soll_speed(joy_in.get("soll_speed", 0.0)),
            selected_axes=selected_axes,
        )
    return joy


def _decode_lease_axis_map(payload_value: object) -> Dict[str, list[str]]:
    decoded: Dict[str, list[str]] = {}
    if isinstance(payload_value, dict):
        for k, v in payload_value.items():
            if isinstance(v, (list, tuple)):
                decoded[str(k)] = [str(x) for x in list(v)]
    return decoded


def _decode_str_float_map(payload_value: object) -> Dict[str, float]:
    return {k: float(v) for k, v in dict(payload_value or {}).items()}


def _decode_axis_bool_map(payload_value: object) -> Dict[str, bool]:
    return {str(k): bool(v) for k, v in dict(payload_value or {}).items()}


def _decode_axis_int_map(payload_value: object) -> Dict[str, int]:
    return {str(k): int(v) for k, v in dict(payload_value or {}).items()}


def _decode_axis_str_map(payload_value: object) -> Dict[str, str]:
    return {str(k): str(v) for k, v in dict(payload_value or {}).items()}


def _decode_axis_nested_float_map(payload_value: object) -> Dict[str, Dict[str, float]]:
    return {
        str(k): {str(pk): float(pv) for pk, pv in dict(v).items()}
        for k, v in dict(payload_value or {}).items()
        if isinstance(v, dict)
    }


def _decode_axis_nested_str_map(payload_value: object) -> Dict[str, Dict[str, str]]:
    return {
        str(k): {str(pk): str(pv) for pk, pv in dict(v).items()}
        for k, v in dict(payload_value or {}).items()
        if isinstance(v, dict)
    }


def _decode_axis_list_map(payload_value: object) -> Dict[str, list[str]]:
    return {
        str(k): [str(x) for x in list(v)]
        for k, v in dict(payload_value or {}).items()
        if isinstance(v, (list, tuple))
    }


def decode_telemetry(payload: Dict[str, Any]) -> TelemetrySnapshot:
    axes_out = _decode_axes(payload.get("axes", {}))
    densis_out = _decode_densis(payload.get("densis", {}))
    joy = _decode_joy_state(payload.get("joy", {}))
    lease_rig = str(payload.get("lease_rig", ""))
    lease_rig_holder = str(payload.get("lease_rig_holder", lease_rig))
    lease_axis = _decode_lease_axis_map(payload.get("lease_axis", {}))
    lease_axis_holders = _decode_lease_axis_map(payload.get("lease_axis_holders", {}))

    return TelemetrySnapshot(
        tick=int(payload.get("tick", 0)),
        t_s=float(payload.get("t_s", 0.0)),
        core_mode=str(payload.get("core_mode", "")),
        estop=bool(payload.get("estop", False)),
        fault=bool(payload.get("fault", False)),
        axes=axes_out,
        rig_mode=str(payload.get("rig_mode", "DISCOVERY")),
        densis=densis_out,
        lease_rig=lease_rig,
        lease_axis=lease_axis,
        lease_rig_holder=lease_rig_holder,
        lease_axis_holders=lease_axis_holders if lease_axis_holders else dict(lease_axis),
        lease_denial_reason=str(payload.get("lease_denial_reason", "")),
        estop_status_word=int(payload.get("estop_status_word", 0)),
        param_edit_active=bool(payload.get("param_edit_active", False)),
        param_edit_group=str(payload.get("param_edit_group", "")),
        params=_decode_str_float_map(payload.get("params", {})),
        plc_uplink_fields=_decode_axis_str_map(payload.get("plc_uplink_fields", {})),
        plc_uplink_tail=_decode_axis_str_map(payload.get("plc_uplink_tail", {})),
        axis_estop_status_word=_decode_axis_int_map(payload.get("axis_estop_status_word", {})),
        axis_param_edit_active=_decode_axis_bool_map(payload.get("axis_param_edit_active", {})),
        axis_param_edit_group=_decode_axis_str_map(payload.get("axis_param_edit_group", {})),
        axis_params=_decode_axis_nested_float_map(payload.get("axis_params", {})),
        axis_plc_uplink_fields=_decode_axis_nested_str_map(
            payload.get("axis_plc_uplink_fields", {})
        ),
        axis_plc_uplink_tail=_decode_axis_nested_str_map(payload.get("axis_plc_uplink_tail", {})),
        axis_param_commit_req_id=_decode_axis_str_map(payload.get("axis_param_commit_req_id", {})),
        axis_param_commit_group=_decode_axis_str_map(payload.get("axis_param_commit_group", {})),
        axis_param_commit_status=_decode_axis_str_map(payload.get("axis_param_commit_status", {})),
        axis_param_commit_age_ticks=_decode_axis_int_map(
            payload.get("axis_param_commit_age_ticks", {})
        ),
        axis_param_commit_unmatched=_decode_axis_list_map(
            payload.get("axis_param_commit_unmatched", {})
        ),
        core_acks=[str(x) for x in list(payload.get("core_acks", []))],
        param_commit_req_id=str(payload.get("param_commit_req_id", "")),
        param_commit_group=str(payload.get("param_commit_group", "")),
        param_commit_status=str(payload.get("param_commit_status", "idle")),
        param_commit_age_ticks=int(payload.get("param_commit_age_ticks", 0)),
        param_commit_unmatched=[str(x) for x in list(payload.get("param_commit_unmatched", []))],
        joy=joy,
    )


def encode_raw_controls(rc: RawControls) -> Dict[str, Any]:
    return asdict(rc)


def decode_raw_controls(payload: Dict[str, Any]) -> RawControls:
    axes_in = payload.get("axes", [])
    buttons_in = payload.get("buttons", [])
    return RawControls(
        type=str(payload.get("type", "raw_controls")),
        t_ns=int(payload.get("t_ns", 0)),
        src=str(payload.get("src", "")),
        axes=[float(x) for x in list(axes_in)],
        buttons=[int(x) for x in list(buttons_in)],
    )


def encode_command_frame(frame: CommandFrame) -> Dict[str, Any]:
    d = asdict(frame)
    if not d.get("lifetick_echo"):
        d.pop("lifetick_echo", None)
    if not d.get("resync_by_axis"):
        d.pop("resync_by_axis", None)
    if not d.get("main_reset_by_axis"):
        d.pop("main_reset_by_axis", None)
    if not d.get("guider_reset_by_axis"):
        d.pop("guider_reset_by_axis", None)
    if d.get("intent", True) is True:
        d.pop("intent", None)
    if not d.get("resync", False):
        d.pop("resync", None)
    if not d.get("gui_not_halt", False):
        d.pop("gui_not_halt", None)
    return d


def _decode_command_axes(payload: Dict[str, Any]) -> Dict[str, AxisSetpoint]:
    axes_in = payload["axes"]
    return {axis_id: AxisSetpoint(**ax) for axis_id, ax in axes_in.items()}


def decode_command_frame(payload: Dict[str, Any]) -> CommandFrame:
    axes_out = _decode_command_axes(payload)
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
        estop_reset=bool(payload.get("estop_reset", False)),
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
