from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Dict, cast

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, decode_param_ops
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot


def _as_object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(k): v for k, v in mapping.items()}


def _as_object_sequence(value: object) -> list[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(cast(Sequence[object], value))


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except Exception:
            return float(default)
    return float(default)


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except Exception:
            return int(default)
    return int(default)


def _decode_axis_setpoint(value: object) -> AxisSetpoint | None:
    value_dict = _as_object_dict(value)
    if not value_dict:
        return None
    return AxisSetpoint(
        enable=bool(value_dict.get("enable", False)),
        vel=_as_float(value_dict.get("vel", 0.0)),
    )


def _decode_axis_telemetry(value: object) -> AxisTelemetry | None:
    value_dict = _as_object_dict(value)
    if not value_dict:
        return None
    return AxisTelemetry(
        pos=_as_float(value_dict.get("pos", 0.0)),
        vel=_as_float(value_dict.get("vel", 0.0)),
        enabled=bool(value_dict.get("enabled", False)),
        fault=bool(value_dict.get("fault", False)),
        vel_cmd=_as_float(value_dict.get("vel_cmd", 0.0)),
        enable_cmd=bool(value_dict.get("enable_cmd", False)),
        device_tick=_as_int(value_dict.get("device_tick", 0)),
        lifetick_rx=_as_int(value_dict.get("lifetick_rx", 0)),
        lifetick_age=_as_int(value_dict.get("lifetick_age", 0)),
        status_word=_as_int(value_dict.get("status_word", 0)),
        guide_status_word=_as_int(value_dict.get("guide_status_word", 0)),
    )


def _as_string_list(value: object) -> list[str]:
    return [str(x) for x in _as_object_sequence(value)]


def _decode_anchor_xyz(value: object) -> tuple[float, float, float] | None:
    vals = _as_object_sequence(value)
    if not vals:
        return None
    if len(vals) != 3:
        return None
    return (_as_float(vals[0]), _as_float(vals[1]), _as_float(vals[2]))


def decode_telemetry_payload(payload: Dict[str, Any]) -> TelemetrySnapshot:
    axes_out = _decode_axes(payload.get("axes", {}))
    densis_out = _decode_densis(payload.get("densis", {}))
    joy = _decode_joy(payload.get("joy", {}))
    lease_axis = _decode_list_map(payload.get("lease_axis", {}))
    lease_axis_holders = _decode_list_map(payload.get("lease_axis_holders", {}))
    return TelemetrySnapshot(
        tick=_as_int(payload.get("tick", 0)),
        t_s=_as_float(payload.get("t_s", 0.0)),
        core_mode=str(payload.get("core_mode", "")),
        estop=bool(payload.get("estop", False)),
        fault=bool(payload.get("fault", False)),
        axes=axes_out,
        rig_mode=str(payload.get("rig_mode", "DISCOVERY")),
        densis=densis_out,
        lease_rig=str(payload.get("lease_rig", "")),
        lease_axis=lease_axis,
        lease_rig_holder=str(payload.get("lease_rig_holder", payload.get("lease_rig", ""))),
        lease_axis_holders=lease_axis_holders if lease_axis_holders else dict(lease_axis),
        lease_denial_reason=str(payload.get("lease_denial_reason", "")),
        estop_status_word=_as_int(payload.get("estop_status_word", 0)),
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
        param_commit_age_ticks=_as_int(payload.get("param_commit_age_ticks", 0)),
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
        tick=_as_int(payload["tick"]),
        t_s=_as_float(payload["t_s"]),
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
            str(k): _as_int(v) for k, v in _as_object_dict(payload.get("lifetick_echo", {})).items()
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


def _decode_axes(value: object) -> Dict[str, AxisTelemetry]:
    return {
        str(axis_id): axis_telemetry
        for axis_id, ax in _as_object_dict(value).items()
        if (axis_telemetry := _decode_axis_telemetry(ax)) is not None
    }


def _decode_densis(value: object) -> Dict[str, DensiTelemetry]:
    densis_out: Dict[str, DensiTelemetry] = {}
    for dev_id, d in _as_object_dict(value).items():
        d_dict = _as_object_dict(d)
        if not d_dict:
            continue
        densis_out[str(dev_id)] = DensiTelemetry(
            device_id=str(d_dict.get("device_id", dev_id)),
            online=bool(d_dict.get("online", False)),
            claimed_by_hip=str(d_dict.get("claimed_by_hip", "")),
            participating=bool(d_dict.get("participating", False)),
            anchor_xyz=_decode_anchor_xyz(d_dict.get("anchor_xyz", None)),
            last_seen_age_ticks=_as_int(d_dict.get("last_seen_age_ticks", 0)),
        )
    return densis_out


def _decode_joy(value: object) -> JoyState:
    value_dict = _as_object_dict(value)
    if not value_dict:
        return JoyState()
    selected_axes = tuple(
        str(x) for x in _as_string_list(value_dict.get("selected_axes", ())) if str(x).strip()
    )
    return JoyState(
        deadman=bool(value_dict.get("deadman", False)),
        soll_speed=clamp_soll_speed(_as_float(value_dict.get("soll_speed", 0.0))),
        look_pan=clamp_soll_speed(_as_float(value_dict.get("look_pan", 0.0))),
        look_tilt=clamp_soll_speed(_as_float(value_dict.get("look_tilt", 0.0))),
        selected_axes=selected_axes,
    )


def _decode_str_map(value: object) -> Dict[str, str]:
    return {str(k): str(v) for k, v in _as_object_dict(value).items()}


def _decode_str_float_map(value: object) -> Dict[str, float]:
    return {str(k): _as_float(v) for k, v in _as_object_dict(value).items()}


def _decode_bool_map(value: object) -> Dict[str, bool]:
    return {str(k): bool(v) for k, v in _as_object_dict(value).items()}


def _decode_int_map(value: object) -> Dict[str, int]:
    return {str(k): _as_int(v) for k, v in _as_object_dict(value).items()}


def _decode_nested_float_map(value: object) -> Dict[str, Dict[str, float]]:
    return {
        str(k): {str(pk): _as_float(pv) for pk, pv in _as_object_dict(v).items()}
        for k, v in _as_object_dict(value).items()
        if _as_object_dict(v)
    }


def _decode_nested_str_map(value: object) -> Dict[str, Dict[str, str]]:
    return {
        str(k): {str(pk): str(pv) for pk, pv in _as_object_dict(v).items()}
        for k, v in _as_object_dict(value).items()
        if _as_object_dict(v)
    }


def _decode_list_map(value: object) -> Dict[str, list[str]]:
    out: Dict[str, list[str]] = {}
    for k, v in _as_object_dict(value).items():
        seq = _as_object_sequence(v)
        if seq:
            out[str(k)] = [str(x) for x in seq]
    return out
