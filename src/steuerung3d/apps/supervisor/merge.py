from __future__ import annotations

from typing import Any

from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry import TelemetrySnapshot


def _latest_scalar(
    snap: TelemetrySnapshot, latest: TelemetrySnapshot, name: str, default: Any
) -> Any:
    return getattr(snap, name, getattr(latest, name, default))


def _merge_mapping(snap: TelemetrySnapshot, latest: TelemetrySnapshot, name: str) -> dict[Any, Any]:
    return {
        **dict(getattr(latest, name, {})),
        **dict(getattr(snap, name, {})),
    }


def _latest_list(snap: TelemetrySnapshot, latest: TelemetrySnapshot, name: str) -> list[Any]:
    return list(getattr(snap, name, getattr(latest, name, [])) or [])


def merge_snapshots(
    base: TelemetrySnapshot | None,
    snaps: list[TelemetrySnapshot] | tuple[TelemetrySnapshot, ...],
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
            rig_mode=str(_latest_scalar(snap, latest, "rig_mode", "DISCOVERY")),
            densis={**dict(latest.densis), **dict(snap.densis)},
            lease_rig=str(_latest_scalar(snap, latest, "lease_rig", "")),
            lease_axis=_merge_mapping(snap, latest, "lease_axis"),
            lease_rig_holder=str(_latest_scalar(snap, latest, "lease_rig_holder", "")),
            lease_axis_holders=_merge_mapping(snap, latest, "lease_axis_holders"),
            lease_denial_reason=str(_latest_scalar(snap, latest, "lease_denial_reason", "")),
            estop_status_word=int(_latest_scalar(snap, latest, "estop_status_word", 0)),
            param_edit_active=bool(_latest_scalar(snap, latest, "param_edit_active", False)),
            param_edit_group=str(_latest_scalar(snap, latest, "param_edit_group", "")),
            params=_merge_mapping(snap, latest, "params"),
            plc_uplink_fields=_merge_mapping(snap, latest, "plc_uplink_fields"),
            plc_uplink_tail=_merge_mapping(snap, latest, "plc_uplink_tail"),
            axis_estop_status_word=_merge_mapping(snap, latest, "axis_estop_status_word"),
            axis_param_edit_active=_merge_mapping(snap, latest, "axis_param_edit_active"),
            axis_param_edit_group=_merge_mapping(snap, latest, "axis_param_edit_group"),
            axis_params=_merge_mapping(snap, latest, "axis_params"),
            axis_plc_uplink_fields=_merge_mapping(snap, latest, "axis_plc_uplink_fields"),
            axis_plc_uplink_tail=_merge_mapping(snap, latest, "axis_plc_uplink_tail"),
            axis_param_commit_req_id=_merge_mapping(snap, latest, "axis_param_commit_req_id"),
            axis_param_commit_group=_merge_mapping(snap, latest, "axis_param_commit_group"),
            axis_param_commit_status=_merge_mapping(snap, latest, "axis_param_commit_status"),
            axis_param_commit_age_ticks=_merge_mapping(snap, latest, "axis_param_commit_age_ticks"),
            axis_param_commit_unmatched=_merge_mapping(snap, latest, "axis_param_commit_unmatched"),
            core_acks=_latest_list(snap, latest, "core_acks"),
            param_commit_req_id=str(_latest_scalar(snap, latest, "param_commit_req_id", "")),
            param_commit_group=str(_latest_scalar(snap, latest, "param_commit_group", "")),
            param_commit_status=str(_latest_scalar(snap, latest, "param_commit_status", "idle")),
            param_commit_age_ticks=int(_latest_scalar(snap, latest, "param_commit_age_ticks", 0)),
            param_commit_unmatched=_latest_list(snap, latest, "param_commit_unmatched"),
            joy=getattr(snap, "joy", getattr(latest, "joy", None)) or JoyState(),
        )
    return latest
