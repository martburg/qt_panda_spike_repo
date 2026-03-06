from __future__ import annotations

from dataclasses import replace

from steuerung3d.core.telemetry import TelemetrySnapshot


def axis_scoped_snapshot(snap: TelemetrySnapshot, axis_id: str) -> TelemetrySnapshot:
    axis = str(axis_id or "").strip()
    if not axis:
        return snap

    estop_map = dict(getattr(snap, "axis_estop_status_word", {}) or {})
    edit_active_map = dict(getattr(snap, "axis_param_edit_active", {}) or {})
    edit_group_map = dict(getattr(snap, "axis_param_edit_group", {}) or {})
    params_map = dict(getattr(snap, "axis_params", {}) or {})
    fields_map = dict(getattr(snap, "axis_plc_uplink_fields", {}) or {})
    tail_map = dict(getattr(snap, "axis_plc_uplink_tail", {}) or {})
    commit_req_map = dict(getattr(snap, "axis_param_commit_req_id", {}) or {})
    commit_group_map = dict(getattr(snap, "axis_param_commit_group", {}) or {})
    commit_status_map = dict(getattr(snap, "axis_param_commit_status", {}) or {})
    commit_age_map = dict(getattr(snap, "axis_param_commit_age_ticks", {}) or {})
    commit_unmatched_map = dict(getattr(snap, "axis_param_commit_unmatched", {}) or {})

    has_axis_cache = any(
        axis in m
        for m in (
            estop_map,
            edit_active_map,
            edit_group_map,
            params_map,
            fields_map,
            tail_map,
            commit_req_map,
            commit_group_map,
            commit_status_map,
            commit_age_map,
            commit_unmatched_map,
        )
    )
    if not has_axis_cache:
        return snap

    return replace(
        snap,
        estop_status_word=int(estop_map.get(axis, getattr(snap, "estop_status_word", 0))),
        param_edit_active=bool(
            edit_active_map.get(axis, getattr(snap, "param_edit_active", False))
        ),
        param_edit_group=str(edit_group_map.get(axis, getattr(snap, "param_edit_group", ""))),
        params=dict(params_map.get(axis, getattr(snap, "params", {}) or {})),
        plc_uplink_fields=dict(fields_map.get(axis, getattr(snap, "plc_uplink_fields", {}) or {})),
        plc_uplink_tail=dict(tail_map.get(axis, getattr(snap, "plc_uplink_tail", {}) or {})),
        param_commit_req_id=str(commit_req_map.get(axis, getattr(snap, "param_commit_req_id", ""))),
        param_commit_group=str(commit_group_map.get(axis, getattr(snap, "param_commit_group", ""))),
        param_commit_status=str(
            commit_status_map.get(axis, getattr(snap, "param_commit_status", "idle"))
        ),
        param_commit_age_ticks=int(
            commit_age_map.get(axis, getattr(snap, "param_commit_age_ticks", 0))
        ),
        param_commit_unmatched=list(
            commit_unmatched_map.get(axis, getattr(snap, "param_commit_unmatched", []) or [])
        ),
    )
