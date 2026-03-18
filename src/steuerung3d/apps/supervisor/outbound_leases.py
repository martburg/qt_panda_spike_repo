from __future__ import annotations

from collections.abc import Sequence

from steuerung3d.core.intents import Intent, ReleaseAxisLease, RequestAxisLease

from .models import AxisConfig


def sync_leases(
    *,
    intents: list[Intent],
    supervisor_id: str,
    locked: bool,
    selected_axes: Sequence[AxisConfig],
    leased_axis_ids: set[str],
) -> set[str]:
    selected_axis_ids = tuple(axis.axis_id for axis in selected_axes)
    desired_leased_axis_ids: set[str] = set() if locked else set(selected_axis_ids)

    released_axis_ids = sorted(leased_axis_ids - desired_leased_axis_ids)
    for axis_id in released_axis_ids:
        intents.append(ReleaseAxisLease(axis_id=axis_id, hip_id=supervisor_id))
    requested_axis_ids = sorted(desired_leased_axis_ids - leased_axis_ids)
    for axis_id in requested_axis_ids:
        intents.append(RequestAxisLease(axis_id=axis_id, hip_id=supervisor_id))
    return desired_leased_axis_ids
