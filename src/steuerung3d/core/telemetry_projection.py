from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from steuerung3d.core.telemetry import TelemetrySnapshot

_DEVICE_SURFACE_FIELDS = (
    "estop_status_word",
    "param_edit_active",
    "param_edit_group",
    "params",
    "plc_uplink_fields",
    "plc_uplink_tail",
    "param_commit_req_id",
    "param_commit_group",
    "param_commit_status",
    "param_commit_age_ticks",
    "param_commit_unmatched",
)


def blank_device_surface(snap: TelemetrySnapshot) -> TelemetrySnapshot:
    return replace(
        snap,
        estop_status_word=0,
        param_edit_active=False,
        param_edit_group="",
        params={},
        plc_uplink_fields={},
        plc_uplink_tail={},
        param_commit_req_id="",
        param_commit_group="",
        param_commit_status="idle",
        param_commit_age_ticks=0,
        param_commit_unmatched=[],
    )


def axis_cache_maps_from_snapshot(snap: TelemetrySnapshot) -> dict[str, dict[str, Any]]:
    return {
        "estop_status_word": _dict(getattr(snap, "axis_estop_status_word", {})),
        "param_edit_active": _dict(getattr(snap, "axis_param_edit_active", {})),
        "param_edit_group": _dict(getattr(snap, "axis_param_edit_group", {})),
        "params": _dict(getattr(snap, "axis_params", {})),
        "plc_uplink_fields": _dict(getattr(snap, "axis_plc_uplink_fields", {})),
        "plc_uplink_tail": _dict(getattr(snap, "axis_plc_uplink_tail", {})),
        "param_commit_req_id": _dict(getattr(snap, "axis_param_commit_req_id", {})),
        "param_commit_group": _dict(getattr(snap, "axis_param_commit_group", {})),
        "param_commit_status": _dict(getattr(snap, "axis_param_commit_status", {})),
        "param_commit_age_ticks": _dict(getattr(snap, "axis_param_commit_age_ticks", {})),
        "param_commit_unmatched": _dict(getattr(snap, "axis_param_commit_unmatched", {})),
    }


def has_axis_device_cache(axis_cache_maps: Mapping[str, Mapping[str, Any]]) -> bool:
    return any(bool(values) for values in axis_cache_maps.values())


def project_device_surface_from_axis(
    snap: TelemetrySnapshot,
    axis_id: str,
    *,
    estop_status_word_by_axis: Mapping[str, Any],
    param_edit_active_by_axis: Mapping[str, Any],
    param_edit_group_by_axis: Mapping[str, Any],
    params_by_axis: Mapping[str, Any],
    plc_uplink_fields_by_axis: Mapping[str, Any],
    plc_uplink_tail_by_axis: Mapping[str, Any],
    param_commit_req_id_by_axis: Mapping[str, Any],
    param_commit_group_by_axis: Mapping[str, Any],
    param_commit_status_by_axis: Mapping[str, Any],
    param_commit_age_ticks_by_axis: Mapping[str, Any],
    param_commit_unmatched_by_axis: Mapping[str, Any],
) -> TelemetrySnapshot:
    axis = str(axis_id or "").strip()
    return replace(
        snap,
        estop_status_word=int(
            estop_status_word_by_axis.get(axis, getattr(snap, "estop_status_word", 0))
        ),
        param_edit_active=bool(
            param_edit_active_by_axis.get(axis, getattr(snap, "param_edit_active", False))
        ),
        param_edit_group=str(
            param_edit_group_by_axis.get(axis, getattr(snap, "param_edit_group", ""))
        ),
        params=dict(params_by_axis.get(axis, _dict(getattr(snap, "params", {}))) or {}),
        plc_uplink_fields=dict(
            plc_uplink_fields_by_axis.get(axis, _dict(getattr(snap, "plc_uplink_fields", {}))) or {}
        ),
        plc_uplink_tail=dict(
            plc_uplink_tail_by_axis.get(axis, _dict(getattr(snap, "plc_uplink_tail", {}))) or {}
        ),
        param_commit_req_id=str(
            param_commit_req_id_by_axis.get(axis, getattr(snap, "param_commit_req_id", ""))
        ),
        param_commit_group=str(
            param_commit_group_by_axis.get(axis, getattr(snap, "param_commit_group", ""))
        ),
        param_commit_status=str(
            param_commit_status_by_axis.get(axis, getattr(snap, "param_commit_status", "idle"))
        ),
        param_commit_age_ticks=int(
            param_commit_age_ticks_by_axis.get(axis, getattr(snap, "param_commit_age_ticks", 0))
        ),
        param_commit_unmatched=list(
            param_commit_unmatched_by_axis.get(
                axis, list(getattr(snap, "param_commit_unmatched", [])) or []
            )
        ),
    )


def snapshot_with_axis_device_caches(
    snap: TelemetrySnapshot,
    *,
    estop_status_word_by_axis: Mapping[str, Any],
    param_edit_active_by_axis: Mapping[str, Any],
    param_edit_group_by_axis: Mapping[str, Any],
    params_by_axis: Mapping[str, Any],
    plc_uplink_fields_by_axis: Mapping[str, Any],
    plc_uplink_tail_by_axis: Mapping[str, Any],
    param_commit_req_id_by_axis: Mapping[str, Any],
    param_commit_group_by_axis: Mapping[str, Any],
    param_commit_status_by_axis: Mapping[str, Any],
    param_commit_age_ticks_by_axis: Mapping[str, Any],
    param_commit_unmatched_by_axis: Mapping[str, Any],
) -> TelemetrySnapshot:
    return replace(
        snap,
        axis_estop_status_word=_map_str_int(estop_status_word_by_axis),
        axis_param_edit_active=_map_str_bool(param_edit_active_by_axis),
        axis_param_edit_group=_map_str_str(param_edit_group_by_axis),
        axis_params=_map_str_dict(params_by_axis),
        axis_plc_uplink_fields=_map_str_dict(plc_uplink_fields_by_axis),
        axis_plc_uplink_tail=_map_str_dict(plc_uplink_tail_by_axis),
        axis_param_commit_req_id=_map_str_str(param_commit_req_id_by_axis),
        axis_param_commit_group=_map_str_str(param_commit_group_by_axis),
        axis_param_commit_status=_map_str_str(param_commit_status_by_axis),
        axis_param_commit_age_ticks=_map_str_int(param_commit_age_ticks_by_axis),
        axis_param_commit_unmatched=_map_str_list_str(param_commit_unmatched_by_axis),
    )


def _dict(value: Any) -> dict[str, Any]:
    return dict(value or {})


def _map_str_int(values: Mapping[str, Any]) -> dict[str, int]:
    return {str(k): int(v) for k, v in _dict(values).items()}


def _map_str_bool(values: Mapping[str, Any]) -> dict[str, bool]:
    return {str(k): bool(v) for k, v in _dict(values).items()}


def _map_str_str(values: Mapping[str, Any]) -> dict[str, str]:
    return {str(k): str(v) for k, v in _dict(values).items()}


def _map_str_dict(values: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(k): dict(v or {}) for k, v in _dict(values).items()}


def _map_str_list_str(values: Mapping[str, Any]) -> dict[str, list[str]]:
    return {str(k): [str(x) for x in list(v or [])] for k, v in _dict(values).items()}
