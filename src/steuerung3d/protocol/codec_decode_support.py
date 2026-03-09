from __future__ import annotations

from typing import Any, Dict

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, decode_param_ops
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot


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
        core_acks=[str(x) for x in list(payload.get("core_acks", []))],
        param_commit_req_id=str(payload.get("param_commit_req_id", "")),
        param_commit_group=str(payload.get("param_commit_group", "")),
        param_commit_status=str(payload.get("param_commit_status", "idle")),
        param_commit_age_ticks=int(payload.get("param_commit_age_ticks", 0)),
        param_commit_unmatched=[str(x) for x in list(payload.get("param_commit_unmatched", []))],
        joy=joy,
    )


def decode_command_frame_payload(payload: Dict[str, Any]) -> CommandFrame:
    axes_out: Dict[str, AxisSetpoint] = {
        axis_id: AxisSetpoint(**ax) for axis_id, ax in payload["axes"].items()
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


def _decode_axes(value: Any) -> Dict[str, AxisTelemetry]:
    return {
        str(axis_id): AxisTelemetry(**ax)
        for axis_id, ax in dict(value).items()
        if isinstance(ax, dict)
    }


def _decode_densis(value: Any) -> Dict[str, DensiTelemetry]:
    densis_out: Dict[str, DensiTelemetry] = {}
    if isinstance(value, dict):
        for dev_id, d in value.items():
            if isinstance(d, dict):
                try:
                    densis_out[str(dev_id)] = DensiTelemetry(**d)
                except Exception:
                    continue
    return densis_out


def _decode_joy(value: Any) -> JoyState:
    joy = JoyState()
    if isinstance(value, dict):
        selected_axes = tuple(
            str(x) for x in list(value.get("selected_axes", ())) if str(x).strip()
        )
        joy = JoyState(
            deadman=bool(value.get("deadman", False)),
            soll_speed=clamp_soll_speed(value.get("soll_speed", 0.0)),
            selected_axes=selected_axes,
        )
    return joy


def _decode_str_map(value: Any) -> Dict[str, str]:
    return {str(k): str(v) for k, v in dict(value).items()}


def _decode_str_float_map(value: Any) -> Dict[str, float]:
    return {str(k): float(v) for k, v in dict(value).items()}


def _decode_bool_map(value: Any) -> Dict[str, bool]:
    return {str(k): bool(v) for k, v in dict(value).items()}


def _decode_int_map(value: Any) -> Dict[str, int]:
    return {str(k): int(v) for k, v in dict(value).items()}


def _decode_nested_float_map(value: Any) -> Dict[str, Dict[str, float]]:
    return {
        str(k): {str(pk): float(pv) for pk, pv in dict(v).items()}
        for k, v in dict(value).items()
        if isinstance(v, dict)
    }


def _decode_nested_str_map(value: Any) -> Dict[str, Dict[str, str]]:
    return {
        str(k): {str(pk): str(pv) for pk, pv in dict(v).items()}
        for k, v in dict(value).items()
        if isinstance(v, dict)
    }


def _decode_list_map(value: Any) -> Dict[str, list[str]]:
    out: Dict[str, list[str]] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, (list, tuple)):
                out[str(k)] = [str(x) for x in list(v)]
    return out
