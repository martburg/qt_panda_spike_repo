from __future__ import annotations

from dataclasses import replace

from steuerung3d.core.telemetry import TelemetrySnapshot


def _blank_device_surface(snap: TelemetrySnapshot) -> TelemetrySnapshot:
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


def axis_scoped_snapshot(snap: TelemetrySnapshot, axis_id: str) -> TelemetrySnapshot:
    """Project device-scoped top-level telemetry to one axis.

    In fanout mode, shared pool telemetry (`axes`, `densis`, caches) is broadcast to all
    HiPs, but device-scoped top-level fields like `params`, `plc_uplink_fields`, and
    `estop_status_word` must be stable per HiP.

    Rules:
    - if axis-scoped caches are present and `axis_id` is non-empty, project the device
      surface from that axis only;
    - if axis-scoped caches are present and `axis_id` is empty, clear the device surface
      instead of floating between whichever DenSi updated last;
    - if no axis-scoped caches are present, preserve legacy behavior and return `snap`.
    """
    axis = str(axis_id or "").strip()

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
        bool(m)
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

    if not axis:
        return _blank_device_surface(snap)

    return replace(
        snap,
        estop_status_word=int(estop_map.get(axis, 0)),
        param_edit_active=bool(edit_active_map.get(axis, False)),
        param_edit_group=str(edit_group_map.get(axis, "")),
        params=dict(params_map.get(axis, {}) or {}),
        plc_uplink_fields=dict(fields_map.get(axis, {}) or {}),
        plc_uplink_tail=dict(tail_map.get(axis, {}) or {}),
        param_commit_req_id=str(commit_req_map.get(axis, "")),
        param_commit_group=str(commit_group_map.get(axis, "")),
        param_commit_status=str(commit_status_map.get(axis, "idle")),
        param_commit_age_ticks=int(commit_age_map.get(axis, 0)),
        param_commit_unmatched=list(commit_unmatched_map.get(axis, []) or []),
    )
