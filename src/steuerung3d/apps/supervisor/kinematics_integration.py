from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.core.intents import EnableAxis, Intent, JogAxis
from steuerung3d.core.telemetry import JoyState, TelemetrySnapshot
from steuerung3d.rig.kinematics.two_axis_head import (
    TwoAxisHeadAxisDemand,
    TwoAxisHeadManualIntent,
    build_two_axis_head_axis_demand,
)
from steuerung3d.rig.scene.two_axis_head_snapshot import (
    SceneSnapshot,
    build_two_axis_head_scene_snapshot,
)

from .models import SupervisorProfile


def _read_semantic_channel(*, joy: JoyState, channel_name: str) -> float:
    raw = getattr(joy, str(channel_name), 0.0)
    try:
        return float(raw)
    except Exception:
        return 0.0


@dataclass(frozen=True)
class KinematicsIntegrationResult:
    intents: tuple[Intent, ...]
    demand: TwoAxisHeadAxisDemand


def build_two_axis_head_manual_intent(
    *,
    profile: SupervisorProfile,
    joy: JoyState,
    actor_id: str,
    enable_motion: bool,
) -> TwoAxisHeadManualIntent:
    control_map = profile.kinematics_control_map
    joint1_channel = control_map.joint1_channel if control_map is not None else "look_pan"
    joint2_channel = control_map.joint2_channel if control_map is not None else "look_tilt"
    return TwoAxisHeadManualIntent(
        look_pan_rate_norm=_read_semantic_channel(joy=joy, channel_name=joint1_channel),
        look_tilt_rate_norm=_read_semantic_channel(joy=joy, channel_name=joint2_channel),
        enable_motion=bool(enable_motion),
        actor_id=str(actor_id),
    )


def build_kinematic_motion_intents(
    *,
    profile: SupervisorProfile,
    motion: TwoAxisHeadManualIntent,
    snap: TelemetrySnapshot | None,
) -> KinematicsIntegrationResult | None:
    geometry = profile.kinematics
    if geometry is None:
        return None
    demand = build_two_axis_head_axis_demand(geometry=geometry, intent=motion, snap=snap)
    intents = tuple(
        JogAxis(axis_id=item.axis_id, vel=item.vel, hip_id=motion.actor_id)
        for item in demand.demands
    )
    return KinematicsIntegrationResult(intents=intents, demand=demand)


def sync_kinematic_motion(
    *,
    intents: list[Intent],
    profile: SupervisorProfile,
    joy: JoyState,
    snap: TelemetrySnapshot | None,
    locked: bool,
    selected_axis_ids: tuple[str, ...],
    active_axis_ids: set[str],
) -> set[str]:
    geometry = profile.kinematics
    if geometry is None:
        return active_axis_ids

    geometry_axis_ids = set(geometry.axis_ids())
    selected_set = set(selected_axis_ids)
    geometry_selected = geometry_axis_ids.issubset(selected_set)
    desired_active_axis_ids: set[str] = (
        set(geometry_axis_ids)
        if (not locked and bool(joy.deadman) and geometry_selected)
        else set()
    )

    disable_axis_ids = tuple(sorted(active_axis_ids - desired_active_axis_ids))
    for axis_id in disable_axis_ids:
        intents.append(EnableAxis(axis_id=axis_id, enable=False, hip_id=str(profile.supervisor_id)))

    if not desired_active_axis_ids:
        return set()

    for axis_id in tuple(sorted(desired_active_axis_ids)):
        intents.append(EnableAxis(axis_id=axis_id, enable=True, hip_id=str(profile.supervisor_id)))

    result = build_kinematic_motion_intents(
        profile=profile,
        motion=build_two_axis_head_manual_intent(
            profile=profile,
            joy=joy,
            actor_id=str(profile.supervisor_id),
            enable_motion=True,
        ),
        snap=snap,
    )
    if result is not None:
        intents.extend(result.intents)
    return desired_active_axis_ids


def build_scene_snapshot(
    *, profile: SupervisorProfile, snap: TelemetrySnapshot
) -> SceneSnapshot | None:
    geometry = profile.kinematics
    if geometry is None:
        return None
    return build_two_axis_head_scene_snapshot(geometry=geometry, snap=snap)
