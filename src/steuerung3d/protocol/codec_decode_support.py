from __future__ import annotations

from typing import Any, Dict

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, decode_param_ops
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot


def _as_object_dict(value: Any) -> dict[object, object]:
    return dict(value) if isinstance(value, dict) else {}


def _decode_axis_setpoint(value: object) -> AxisSetpoint | None:
    if not isinstance(value, dict):
        return None
    return AxisSetpoint(
        enable=bool(value.get("enable", False)),
        vel=float(value.get("vel", 0.0)),
    )


def _decode_axis_telemetry(value: object) -> AxisTelemetry | None:
    if not isinstance(value, dict):
        return None
    return AxisTelemetry(
        pos=float(value.get("pos", 0.0)),
        vel=float(value.get("vel", 0.0)),
        enabled=bool(value.get("enabled", False)),
        fault=bool(value.get("fault", False)),
        vel_cmd=float(value.get("vel_cmd", 0.0)),
        enable_cmd=bool(value.get("enable_cmd", False)),
        device_tick=int(value.get("device_tick", 0)),
        lifetick_rx=int(value.get("lifetick_rx", 0)),
        lifetick_age=int(value.get("lifetick_age", 0)),
        status_word=int(value.get("status_word", 0)),
        guide_status_word=int(value.get("guide_status_word", 0)),
    )


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    return []


def decode_telemetry_payload(payload: Dict[str, Any]) -> TelemetrySnapshot:
    axes_out = _decode_axes(payload.get("axes", {}))
    densis_out = _decode_densis(payload.get("densis", {}))
    joy = _decode_joy(payload.get("joy", {}))
    lease_axis = _decode_list_map(payload.get("lease_axis", {}))
    lease_axis_holders = _decode_list_map(payload.get("lease_axis_holders", {}))
    return TelemetrySnapshot(
        tick=int(payload.get("tick", 0)),
        t_s=float(payload.get("t_s", 0.0)),
        core_mode=str(payload.get("core_mode", "")),
        estop=bool(payload.get("estop", False)),
        fault=bool(payload.get("fault", False)),
        axes=axes_out,
        rig_mode=str(payload.get("rig_mode", "DISCOVERY")),
        densis=densis_out,
        lease_rig=str(payload.get("lease_rig", "")),
        lease_axis=lease_axis,
        lease_rig_holder=str(payload.get("lease_rig_holder", str(payload.get("lease_rig", "")))),
        lease_axis_holders=lease_axis_holders if lease_axis_holders else dict(lease_axis),
        lease_denial_reason=str(payload.get("lease_denial_reason", "")),
        estop_status_word=int(payload.get("estop_status_word", 0)),
        param_edit_active=bool(payload.get("param_edit_active", False)),
        param_edit_group=str(payload.get("param_edit_group", "")),
        params=_decode_str_float_map(payload.get("params", {})),
        plc_uplink_fields=_decode_str_map(payload.get("plc_uplink_fields", {})),
        plc_uplink_tail=_decode_str_map(payload.get("plc_uplink_tail", {})),
        axis_estop_status_word=_decode_int_map(payload.get("axis_estop_status_word", {})),
        axis_param_edit_active=_decode_bool_map(payload.get("axis_param_edit_active", {})),
        axis_param_edit_group=_decode_str_map(payload.get("axis_param_edit_group", {})),
        axis_params=_decode_nested_float_map(payload.get("axis_params", {})),
        axis_plc_uplink_fields=_decode_nested_str_map(payload.get("axis_plc_uplink_fields", {})),
        axis_plc_uplink_tail=_decode_nested_str_map(payload.get("axis_plc_uplink_tail", {})),
        axis_param_commit_req_id=_decode_str_map(payload.get("axis_param_commit_req_id", {})),
        axis_param_commit_group=_decode_str_map(payload.get("axis_param_commit_group", {})),
        axis_param_commit_status=_decode_str_map(payload.get("axis_param_commit_status", {})),
        axis_param_commit_age_ticks=_decode_int_map(payload.get("axis_param_commit_age_ticks", {})),
        axis_param_commit_unmatched=_decode_list_map(
            payload.get("axis_param_commit_unmatched", {})
        ),
        core_acks=_as_string_list(payload.get("core_acks", [])),
        param_commit_req_id=str(payload.get("param_commit_req_id", "")),
        param_commit_group=str(payload.get("param_commit_group", "")),
        param_commit_status=str(payload.get("param_commit_status", "idle")),
        param_commit_age_ticks=int(payload.get("param_commit_age_ticks", 0)),
        param_commit_unmatched=_as_string_list(payload.get("param_commit_unmatched", [])),
        joy=joy,
    )


def decode_command_frame_payload(payload: Dict[str, Any]) -> CommandFrame:
    axes_payload = _as_object_dict(payload.get("axes", {}))
    axes_out: Dict[str, AxisSetpoint] = {}
    for axis_id, ax in axes_payload.items():
        setpoint = _decode_axis_setpoint(ax)
        if setpoint is not None:
            axes_out[str(axis_id)] = setpoint
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
        lifetick_echo={
            str(k): int(v) for k, v in _as_object_dict(payload.get("lifetick_echo", {})).items()
        },
        resync_by_axis={
            str(k): bool(v) for k, v in _as_object_dict(payload.get("resync_by_axis", {})).items()
        },
        main_reset_by_axis={
            str(k): bool(v)
            for k, v in _as_object_dict(payload.get("main_reset_by_axis", {})).items()
        },
        guider_reset_by_axis={
            str(k): bool(v)
            for k, v in _as_object_dict(payload.get("guider_reset_by_axis", {})).items()
        },
    )


def _decode_axes(value: Any) -> Dict[str, AxisTelemetry]:
    return {
        str(axis_id): axis_telemetry
        for axis_id, ax in _as_object_dict(value).items()
        if (axis_telemetry := _decode_axis_telemetry(ax)) is not None
    }


def _decode_densis(value: Any) -> Dict[str, DensiTelemetry]:
    densis_out: Dict[str, DensiTelemetry] = {}
    if isinstance(value, dict):
        for dev_id, d in _as_object_dict(value).items():
            if isinstance(d, dict):
                try:
                    densis_out[str(dev_id)] = DensiTelemetry(
                        device_id=str(d.get("device_id", dev_id)),
                        online=bool(d.get("online", False)),
                        claimed_by_hip=str(d.get("claimed_by_hip", "")),
                        participating=bool(d.get("participating", False)),
                        anchor_xyz=d.get("anchor_xyz", None),
                        last_seen_age_ticks=int(d.get("last_seen_age_ticks", 0)),
                    )
                except Exception:
                    continue
    return densis_out


def _decode_joy(value: Any) -> JoyState:
    joy = JoyState()
    if isinstance(value, dict):
        value_dict = _as_object_dict(value)
        selected_axes = tuple(
            str(x) for x in _as_string_list(value_dict.get("selected_axes", ())) if str(x).strip()
        )
        joy = JoyState(
            deadman=bool(value_dict.get("deadman", False)),
            soll_speed=clamp_soll_speed(value_dict.get("soll_speed", 0.0)),
            selected_axes=selected_axes,
        )
    return joy


def _decode_str_map(value: Any) -> Dict[str, str]:
    return {str(k): str(v) for k, v in _as_object_dict(value).items()}


def _decode_str_float_map(value: Any) -> Dict[str, float]:
    return {str(k): float(v) for k, v in _as_object_dict(value).items()}


def _decode_bool_map(value: Any) -> Dict[str, bool]:
    return {str(k): bool(v) for k, v in _as_object_dict(value).items()}


def _decode_int_map(value: Any) -> Dict[str, int]:
    return {str(k): int(v) for k, v in _as_object_dict(value).items()}


def _decode_nested_float_map(value: Any) -> Dict[str, Dict[str, float]]:
    return {
        str(k): {str(pk): float(pv) for pk, pv in _as_object_dict(v).items()}
        for k, v in _as_object_dict(value).items()
        if isinstance(v, dict)
    }


def _decode_nested_str_map(value: Any) -> Dict[str, Dict[str, str]]:
    return {
        str(k): {str(pk): str(pv) for pk, pv in _as_object_dict(v).items()}
        for k, v in _as_object_dict(value).items()
        if isinstance(v, dict)
    }


def _decode_list_map(value: Any) -> Dict[str, list[str]]:
    out: Dict[str, list[str]] = {}
    if isinstance(value, dict):
        for k, v in _as_object_dict(value).items():
            if isinstance(v, (list, tuple)):
                out[str(k)] = [str(x) for x in v]
    return out
