from __future__ import annotations

from collections.abc import Sequence

from steuerung3d.core.intents import RequestEstopReset, RequestResync

from .models import SupervisorProfile
from .smoke_sequence_types import SelectedActionTarget


def build_selected_estop_reset_intents(profile: SupervisorProfile) -> tuple[RequestEstopReset, ...]:
    intents: list[RequestEstopReset] = []
    for axis in profile.axes:
        if not bool(axis.selected):
            continue
        intents.append(
            RequestEstopReset(
                axis_id=str(axis.axis_id),
                hip_id=str(profile.supervisor_id),
                actor_kind="supervisor",
            )
        )
    return tuple(intents)


def build_selected_resync_intents(profile: SupervisorProfile) -> tuple[RequestResync, ...]:
    intents: list[RequestResync] = []
    for axis in profile.axes:
        if not bool(axis.selected):
            continue
        intents.append(
            RequestResync(
                axis_id=str(axis.axis_id),
                hip_id=str(profile.supervisor_id),
                actor_kind="supervisor",
            )
        )
    return tuple(intents)


def build_selected_estart_targets(profile: SupervisorProfile) -> tuple[SelectedActionTarget, ...]:
    targets: list[SelectedActionTarget] = []
    for axis in profile.axes:
        if not bool(axis.selected):
            continue
        addr = str(axis.densi_action_out or "").strip()
        if not addr:
            continue
        targets.append(
            SelectedActionTarget(
                axis_id=str(axis.axis_id),
                unit_id=str(axis.unit_id),
                densi_process_name=f"densi-{axis.axis_id}",
                action_out_addr=addr,
            )
        )
    return tuple(targets)


def densi_process_names_for_axes(axis_ids: Sequence[str]) -> tuple[str, ...]:
    return tuple(f"densi-{axis_id}" for axis_id in axis_ids)
