from __future__ import annotations

from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.core.telemetry_projection import (
    axis_cache_maps_from_snapshot,
    blank_device_surface,
    has_axis_device_cache,
    project_device_surface_from_axis,
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

    axis_cache_maps = axis_cache_maps_from_snapshot(snap)
    if not has_axis_device_cache(axis_cache_maps):
        return snap

    if not axis:
        return blank_device_surface(snap)

    return project_device_surface_from_axis(
        snap,
        axis,
        estop_status_word_by_axis=axis_cache_maps["estop_status_word"],
        param_edit_active_by_axis=axis_cache_maps["param_edit_active"],
        param_edit_group_by_axis=axis_cache_maps["param_edit_group"],
        params_by_axis=axis_cache_maps["params"],
        plc_uplink_fields_by_axis=axis_cache_maps["plc_uplink_fields"],
        plc_uplink_tail_by_axis=axis_cache_maps["plc_uplink_tail"],
        param_commit_req_id_by_axis=axis_cache_maps["param_commit_req_id"],
        param_commit_group_by_axis=axis_cache_maps["param_commit_group"],
        param_commit_status_by_axis=axis_cache_maps["param_commit_status"],
        param_commit_age_ticks_by_axis=axis_cache_maps["param_commit_age_ticks"],
        param_commit_unmatched_by_axis=axis_cache_maps["param_commit_unmatched"],
    )
