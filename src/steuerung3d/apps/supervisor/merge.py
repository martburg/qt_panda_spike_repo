from __future__ import annotations

from steuerung3d.core.telemetry import TelemetrySnapshot


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
            rig_mode=str(getattr(snap, "rig_mode", getattr(latest, "rig_mode", "DISCOVERY"))),
            densis={**dict(latest.densis), **dict(snap.densis)},
            lease_rig=str(getattr(snap, "lease_rig", getattr(latest, "lease_rig", ""))),
            lease_axis={
                **dict(getattr(latest, "lease_axis", {})),
                **dict(getattr(snap, "lease_axis", {})),
            },
            lease_rig_holder=str(
                getattr(snap, "lease_rig_holder", getattr(latest, "lease_rig_holder", ""))
            ),
            lease_axis_holders={
                **dict(getattr(latest, "lease_axis_holders", {})),
                **dict(getattr(snap, "lease_axis_holders", {})),
            },
            lease_denial_reason=str(
                getattr(snap, "lease_denial_reason", getattr(latest, "lease_denial_reason", ""))
            ),
            estop_status_word=int(
                getattr(snap, "estop_status_word", getattr(latest, "estop_status_word", 0))
            ),
            param_edit_active=bool(
                getattr(snap, "param_edit_active", getattr(latest, "param_edit_active", False))
            ),
            param_edit_group=str(
                getattr(snap, "param_edit_group", getattr(latest, "param_edit_group", ""))
            ),
            params={**dict(getattr(latest, "params", {})), **dict(getattr(snap, "params", {}))},
            plc_uplink_fields={
                **dict(getattr(latest, "plc_uplink_fields", {})),
                **dict(getattr(snap, "plc_uplink_fields", {})),
            },
            plc_uplink_tail={
                **dict(getattr(latest, "plc_uplink_tail", {})),
                **dict(getattr(snap, "plc_uplink_tail", {})),
            },
            axis_estop_status_word={
                **dict(getattr(latest, "axis_estop_status_word", {})),
                **dict(getattr(snap, "axis_estop_status_word", {})),
            },
            axis_param_edit_active={
                **dict(getattr(latest, "axis_param_edit_active", {})),
                **dict(getattr(snap, "axis_param_edit_active", {})),
            },
            axis_param_edit_group={
                **dict(getattr(latest, "axis_param_edit_group", {})),
                **dict(getattr(snap, "axis_param_edit_group", {})),
            },
            axis_params={
                **dict(getattr(latest, "axis_params", {})),
                **dict(getattr(snap, "axis_params", {})),
            },
            axis_plc_uplink_fields={
                **dict(getattr(latest, "axis_plc_uplink_fields", {})),
                **dict(getattr(snap, "axis_plc_uplink_fields", {})),
            },
            axis_plc_uplink_tail={
                **dict(getattr(latest, "axis_plc_uplink_tail", {})),
                **dict(getattr(snap, "axis_plc_uplink_tail", {})),
            },
            axis_param_commit_req_id={
                **dict(getattr(latest, "axis_param_commit_req_id", {})),
                **dict(getattr(snap, "axis_param_commit_req_id", {})),
            },
            axis_param_commit_group={
                **dict(getattr(latest, "axis_param_commit_group", {})),
                **dict(getattr(snap, "axis_param_commit_group", {})),
            },
            axis_param_commit_status={
                **dict(getattr(latest, "axis_param_commit_status", {})),
                **dict(getattr(snap, "axis_param_commit_status", {})),
            },
            axis_param_commit_age_ticks={
                **dict(getattr(latest, "axis_param_commit_age_ticks", {})),
                **dict(getattr(snap, "axis_param_commit_age_ticks", {})),
            },
            axis_param_commit_unmatched={
                **dict(getattr(latest, "axis_param_commit_unmatched", {})),
                **dict(getattr(snap, "axis_param_commit_unmatched", {})),
            },
            core_acks=list(getattr(snap, "core_acks", []) or []),
            param_commit_req_id=str(
                getattr(snap, "param_commit_req_id", getattr(latest, "param_commit_req_id", ""))
            ),
            param_commit_group=str(
                getattr(snap, "param_commit_group", getattr(latest, "param_commit_group", ""))
            ),
            param_commit_status=str(
                getattr(snap, "param_commit_status", getattr(latest, "param_commit_status", "idle"))
            ),
            param_commit_age_ticks=int(
                getattr(
                    snap, "param_commit_age_ticks", getattr(latest, "param_commit_age_ticks", 0)
                )
            ),
            param_commit_unmatched=list(
                getattr(
                    snap, "param_commit_unmatched", getattr(latest, "param_commit_unmatched", [])
                )
                or []
            ),
            joy=getattr(snap, "joy", getattr(latest, "joy", None)),
        )
    return latest
