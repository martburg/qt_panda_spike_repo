from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from steuerung3d.core.telemetry import TelemetrySnapshot

T = TypeVar("T")


def _scalar_value(snap: TelemetrySnapshot, latest: TelemetrySnapshot, name: str, default: T) -> T:
    return getattr(snap, name, getattr(latest, name, default))


K = TypeVar("K")
V = TypeVar("V")


def _merge_mapping(
    latest: TelemetrySnapshot,
    snap: TelemetrySnapshot,
    name: str,
) -> dict[K, V]:
    return {
        **dict(getattr(latest, name, {}) or {}),
        **dict(getattr(snap, name, {}) or {}),
    }


def _replace_sequence(
    snap: TelemetrySnapshot,
    latest: TelemetrySnapshot,
    name: str,
) -> list[Any]:
    return list(_scalar_value(snap, latest, name, []) or [])


def merge_snapshots(
    base: TelemetrySnapshot | None,
    snaps: Sequence[TelemetrySnapshot],
) -> TelemetrySnapshot | None:
    latest = base
    for snap in snaps:
        if latest is None:
            latest = snap
            continue
        latest = TelemetrySnapshot(
            tick=int(snap.tick),
            t_s=float(snap.t_s),
            core_mode=str(snap.core_mode),
            estop=bool(snap.estop),
            fault=bool(snap.fault),
            axes={**dict(latest.axes), **dict(snap.axes)},
            rig_mode=str(_scalar_value(snap, latest, "rig_mode", "DISCOVERY")),
            densis={**dict(latest.densis), **dict(snap.densis)},
            lease_rig=str(_scalar_value(snap, latest, "lease_rig", "")),
            lease_axis=_merge_mapping(latest, snap, "lease_axis"),
            lease_rig_holder=str(_scalar_value(snap, latest, "lease_rig_holder", "")),
            lease_axis_holders=_merge_mapping(latest, snap, "lease_axis_holders"),
            lease_denial_reason=str(_scalar_value(snap, latest, "lease_denial_reason", "")),
            estop_status_word=int(_scalar_value(snap, latest, "estop_status_word", 0)),
            param_edit_active=bool(_scalar_value(snap, latest, "param_edit_active", False)),
            param_edit_group=str(_scalar_value(snap, latest, "param_edit_group", "")),
            params=_merge_mapping(latest, snap, "params"),
            plc_uplink_fields=_merge_mapping(latest, snap, "plc_uplink_fields"),
            plc_uplink_tail=_merge_mapping(latest, snap, "plc_uplink_tail"),
            axis_estop_status_word=_merge_mapping(latest, snap, "axis_estop_status_word"),
            axis_param_edit_active=_merge_mapping(latest, snap, "axis_param_edit_active"),
            axis_param_edit_group=_merge_mapping(latest, snap, "axis_param_edit_group"),
            axis_params=_merge_mapping(latest, snap, "axis_params"),
            axis_plc_uplink_fields=_merge_mapping(latest, snap, "axis_plc_uplink_fields"),
            axis_plc_uplink_tail=_merge_mapping(latest, snap, "axis_plc_uplink_tail"),
            axis_param_commit_req_id=_merge_mapping(latest, snap, "axis_param_commit_req_id"),
            axis_param_commit_group=_merge_mapping(latest, snap, "axis_param_commit_group"),
            axis_param_commit_status=_merge_mapping(latest, snap, "axis_param_commit_status"),
            axis_param_commit_age_ticks=_merge_mapping(latest, snap, "axis_param_commit_age_ticks"),
            axis_param_commit_unmatched=_merge_mapping(latest, snap, "axis_param_commit_unmatched"),
            core_acks=_replace_sequence(snap, latest, "core_acks"),
            param_commit_req_id=str(_scalar_value(snap, latest, "param_commit_req_id", "")),
            param_commit_group=str(_scalar_value(snap, latest, "param_commit_group", "")),
            param_commit_status=str(_scalar_value(snap, latest, "param_commit_status", "idle")),
            param_commit_age_ticks=int(_scalar_value(snap, latest, "param_commit_age_ticks", 0)),
            param_commit_unmatched=_replace_sequence(snap, latest, "param_commit_unmatched"),
            joy=_scalar_value(snap, latest, "joy", None),
        )
    return latest
