from __future__ import annotations

from typing import TYPE_CHECKING

from steuerung3d.core.axis_id import normalize_axis_id
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.core.telemetry_projection import (
    project_device_surface_from_axis,
    snapshot_with_axis_device_caches,
)

from .axis_router_types import make_snapshot

if TYPE_CHECKING:
    from .axis_router import AxisRouter


def slice_snapshot_for_axis(
    router: "AxisRouter", snap: TelemetrySnapshot, axis_id: str
) -> TelemetrySnapshot:
    ax_t = dict(getattr(snap, "axes", {})).get(axis_id)
    axes = {axis_id: ax_t} if ax_t is not None else {}

    densis = dict(getattr(snap, "densis", {}))
    densis_one = {axis_id: densis[axis_id]} if axis_id in densis else {}

    lease_axis = dict(getattr(snap, "lease_axis", {}) or {})
    lease_one = {axis_id: lease_axis[axis_id]} if axis_id in lease_axis else {}

    base = make_snapshot(
        tick=int(getattr(snap, "tick", 0)),
        t_s=float(getattr(snap, "t_s", 0.0)),
        core_mode=str(getattr(snap, "core_mode", "")),
        estop=bool(getattr(snap, "estop", False)),
        fault=bool(getattr(snap, "fault", False)),
        axes=axes,
        rig_mode=str(getattr(snap, "rig_mode", "DISCOVERY")),
        densis=densis_one,
        lease_rig=str(getattr(snap, "lease_rig", "")),
        lease_axis=lease_one,
        core_acks=list(getattr(snap, "core_acks", [])),
        joy=getattr(snap, "joy", JoyState()),
    )
    return project_device_surface_from_axis(
        base,
        axis_id,
        estop_status_word_by_axis=router.last_dev_estop_word_by_axis,
        param_edit_active_by_axis=router.last_dev_param_edit_active_by_axis,
        param_edit_group_by_axis=router.last_dev_param_edit_group_by_axis,
        params_by_axis=router.last_dev_params_by_axis,
        plc_uplink_fields_by_axis=router.last_dev_plc_uplink_fields_by_axis,
        plc_uplink_tail_by_axis=router.last_dev_plc_uplink_tail_by_axis,
        param_commit_req_id_by_axis=router.last_dev_param_commit_req_id_by_axis,
        param_commit_group_by_axis=router.last_dev_param_commit_group_by_axis,
        param_commit_status_by_axis=router.last_dev_param_commit_status_by_axis,
        param_commit_age_ticks_by_axis=router.last_dev_param_commit_age_ticks_by_axis,
        param_commit_unmatched_by_axis=router.last_dev_param_commit_unmatched_by_axis,
    )


def project_joy_for_axis(snap: TelemetrySnapshot, axis_id: str) -> JoyState:
    joy = getattr(snap, "joy", JoyState())
    if not isinstance(joy, JoyState):
        joy = JoyState()
    return JoyState(
        deadman=bool(getattr(joy, "deadman", False)),
        select_hip=normalize_axis_id(axis_id) in tuple(getattr(joy, "selected_axes", ()) or ()),
        soll_speed=float(getattr(joy, "soll_speed", 0.0)),
        selected_axes=getattr(joy, "selected_axes", ()),
    )


def fanout_snapshot_with_axis_caches(
    router: "AxisRouter", snap: TelemetrySnapshot
) -> TelemetrySnapshot:
    base = make_snapshot(
        tick=int(getattr(snap, "tick", 0)),
        t_s=float(getattr(snap, "t_s", 0.0)),
        core_mode=str(getattr(snap, "core_mode", "")),
        estop=bool(getattr(snap, "estop", False)),
        fault=bool(getattr(snap, "fault", False)),
        axes=dict(getattr(snap, "axes", {}) or {}),
        rig_mode=str(getattr(snap, "rig_mode", "DISCOVERY")),
        densis=dict(getattr(snap, "densis", {}) or {}),
        lease_rig=str(getattr(snap, "lease_rig", "")),
        lease_axis=dict(getattr(snap, "lease_axis", {}) or {}),
        lease_rig_holder=str(getattr(snap, "lease_rig_holder", getattr(snap, "lease_rig", ""))),
        lease_axis_holders=dict(getattr(snap, "lease_axis_holders", {}) or {}),
        lease_denial_reason=str(getattr(snap, "lease_denial_reason", "")),
        estop_status_word=int(getattr(snap, "estop_status_word", 0)),
        param_edit_active=bool(getattr(snap, "param_edit_active", False)),
        param_edit_group=str(getattr(snap, "param_edit_group", "")),
        params=dict(getattr(snap, "params", {}) or {}),
        plc_uplink_fields=dict(getattr(snap, "plc_uplink_fields", {}) or {}),
        plc_uplink_tail=dict(getattr(snap, "plc_uplink_tail", {}) or {}),
        core_acks=list(getattr(snap, "core_acks", [])),
        param_commit_req_id=str(getattr(snap, "param_commit_req_id", "")),
        param_commit_group=str(getattr(snap, "param_commit_group", "")),
        param_commit_status=str(getattr(snap, "param_commit_status", "idle")),
        param_commit_age_ticks=int(getattr(snap, "param_commit_age_ticks", 0)),
        param_commit_unmatched=list(getattr(snap, "param_commit_unmatched", []) or []),
        joy=getattr(snap, "joy", JoyState()),
    )
    return snapshot_with_axis_device_caches(
        base,
        estop_status_word_by_axis=router.last_dev_estop_word_by_axis,
        param_edit_active_by_axis=router.last_dev_param_edit_active_by_axis,
        param_edit_group_by_axis=router.last_dev_param_edit_group_by_axis,
        params_by_axis=router.last_dev_params_by_axis,
        plc_uplink_fields_by_axis=router.last_dev_plc_uplink_fields_by_axis,
        plc_uplink_tail_by_axis=router.last_dev_plc_uplink_tail_by_axis,
        param_commit_req_id_by_axis=router.last_dev_param_commit_req_id_by_axis,
        param_commit_group_by_axis=router.last_dev_param_commit_group_by_axis,
        param_commit_status_by_axis=router.last_dev_param_commit_status_by_axis,
        param_commit_age_ticks_by_axis=router.last_dev_param_commit_age_ticks_by_axis,
        param_commit_unmatched_by_axis=router.last_dev_param_commit_unmatched_by_axis,
    )
