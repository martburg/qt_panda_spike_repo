from __future__ import annotations

from math import isclose

from steuerung3d.apps.supervisor.kinematics_integration import (
    build_kinematic_motion_intents,
    build_scene_snapshot,
    build_two_axis_head_manual_intent,
)
from steuerung3d.apps.supervisor.models import AxisConfig, SupervisorProfile
from steuerung3d.core.intents import JogAxis
from steuerung3d.core.telemetry import AxisTelemetry, JoyState, TelemetrySnapshot
from steuerung3d.rig.kinematics.two_axis_head import (
    TwoAxisHeadControlMap,
    TwoAxisHeadGeometry,
    TwoAxisHeadManualIntent,
    forward_two_axis_head_pose,
)


def _geometry() -> TwoAxisHeadGeometry:
    return TwoAxisHeadGeometry(
        machine_id="head_a",
        joint1_axis_id="Pan",
        joint2_axis_id="Tilt",
        joint1_min_deg=-180.0,
        joint1_max_deg=180.0,
        joint2_min_deg=-45.0,
        joint2_max_deg=60.0,
        joint1_max_rate_deg_s=90.0,
        joint2_max_rate_deg_s=45.0,
        tool_offset_xyz=(0.0, 0.0, 0.2),
        aim_ray_length_m=2.0,
    )


def _profile(*, control_map: TwoAxisHeadControlMap | None = None) -> SupervisorProfile:
    return SupervisorProfile(
        supervisor_id="sup",
        title="Supervisor",
        cycle_ms=50,
        telem_in="127.0.0.1:51002",
        intent_out="127.0.0.1:51001",
        axes=(
            AxisConfig(unit_id="pan", axis_id="Pan", selected=True),
            AxisConfig(unit_id="tilt", axis_id="Tilt", selected=True),
        ),
        kinematics=_geometry(),
        kinematics_control_map=control_map,
    )


def _snap(*, pan_deg: float, tilt_deg: float) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.05,
        core_mode="RUN",
        estop=False,
        fault=False,
        axes={
            "Pan": AxisTelemetry(pos=pan_deg, vel=0.0, enabled=True, fault=False),
            "Tilt": AxisTelemetry(pos=tilt_deg, vel=0.0, enabled=True, fault=False),
        },
    )


def test_forward_two_axis_head_pose_points_forward_at_zero() -> None:
    pose = forward_two_axis_head_pose(
        geometry=_geometry(),
        joint1_axis_pos_deg=0.0,
        joint2_axis_pos_deg=0.0,
    )
    assert isclose(pose.aim_dir_xyz[0], 1.0)
    assert isclose(pose.aim_dir_xyz[1], 0.0)
    assert isclose(pose.aim_dir_xyz[2], 0.0)


def test_forward_two_axis_head_pose_tracks_joint1_rotation() -> None:
    pose = forward_two_axis_head_pose(
        geometry=_geometry(),
        joint1_axis_pos_deg=90.0,
        joint2_axis_pos_deg=0.0,
    )
    assert isclose(pose.aim_dir_xyz[0], 0.0, abs_tol=1e-9)
    assert isclose(pose.aim_dir_xyz[1], 1.0, abs_tol=1e-9)
    assert isclose(pose.aim_dir_xyz[2], 0.0, abs_tol=1e-9)


def test_forward_two_axis_head_pose_allows_non_vertical_joint1_axis() -> None:
    geometry = TwoAxisHeadGeometry(
        machine_id="head_b",
        joint1_axis_id="Joint1",
        joint2_axis_id="Joint2",
        joint1_axis_base_xyz=(0.0, 1.0, 0.0),
        joint2_axis_joint1_xyz=(0.0, 0.0, 1.0),
        tool_forward_xyz=(1.0, 0.0, 0.0),
    )
    pose = forward_two_axis_head_pose(
        geometry=geometry,
        joint1_axis_pos_deg=90.0,
        joint2_axis_pos_deg=0.0,
    )
    assert isclose(pose.aim_dir_xyz[0], 0.0, abs_tol=1e-9)
    assert isclose(pose.aim_dir_xyz[1], 0.0, abs_tol=1e-9)
    assert isclose(pose.aim_dir_xyz[2], -1.0, abs_tol=1e-9)


def test_build_kinematic_motion_intents_emits_per_axis_jogs() -> None:
    result = build_kinematic_motion_intents(
        profile=_profile(),
        motion=TwoAxisHeadManualIntent(
            look_pan_rate_norm=0.5,
            look_tilt_rate_norm=-1.0,
            enable_motion=True,
            actor_id="sup",
        ),
        snap=_snap(pan_deg=0.0, tilt_deg=0.0),
    )
    assert result is not None
    jogs = [intent for intent in result.intents if isinstance(intent, JogAxis)]
    assert [(j.axis_id, j.vel) for j in jogs] == [("Pan", 45.0), ("Tilt", -45.0)]


def test_build_kinematic_motion_intents_clips_joint2_at_limit() -> None:
    result = build_kinematic_motion_intents(
        profile=_profile(),
        motion=TwoAxisHeadManualIntent(look_tilt_rate_norm=1.0, enable_motion=True, actor_id="sup"),
        snap=_snap(pan_deg=0.0, tilt_deg=60.0),
    )
    assert result is not None
    jogs = [intent for intent in result.intents if isinstance(intent, JogAxis)]
    assert [(j.axis_id, j.vel) for j in jogs] == [("Pan", 0.0), ("Tilt", 0.0)]
    assert result.demand.constraints.warnings == ("joint2_max_reached:Tilt",)


def test_build_two_axis_head_manual_intent_uses_configured_control_map() -> None:
    motion = build_two_axis_head_manual_intent(
        profile=_profile(
            control_map=TwoAxisHeadControlMap(
                joint1_channel="look_tilt",
                joint2_channel="look_pan",
            )
        ),
        joy=JoyState(look_pan=-0.25, look_tilt=0.75),
        actor_id="sup",
        enable_motion=True,
    )
    assert motion.look_pan_rate_norm == 0.75
    assert motion.look_tilt_rate_norm == -0.25


def test_build_scene_snapshot_uses_core_positions() -> None:
    scene = build_scene_snapshot(profile=_profile(), snap=_snap(pan_deg=90.0, tilt_deg=0.0))
    assert scene is not None
    assert scene.actual_pose is not None
    assert isclose(scene.actual_pose.aim_dir_xyz[0], 0.0, abs_tol=1e-9)
    assert isclose(scene.actual_pose.aim_dir_xyz[1], 1.0, abs_tol=1e-9)
    assert [line.name for line in scene.lines] == ["actual_aim"]


def test_build_scene_snapshot_exposes_debug_axis_hints() -> None:
    scene = build_scene_snapshot(profile=_profile(), snap=_snap(pan_deg=90.0, tilt_deg=0.0))
    assert scene is not None
    assert [frame.name for frame in scene.debug_frames] == ["base_hint", "joint1_hint"]
    assert [line.name for line in scene.debug_lines] == ["joint1_axis_base", "joint2_axis_current"]
    assert scene.debug_lines[0].start_xyz == (0.0, 0.0, 0.0)
    assert scene.debug_lines[0].end_xyz == (0.0, 0.0, 2.0)
    assert isclose(scene.debug_lines[1].end_xyz[0], -2.0, abs_tol=1e-9)
    assert isclose(scene.debug_lines[1].end_xyz[1], 0.0, abs_tol=1e-9)
    assert isclose(scene.debug_lines[1].end_xyz[2], 0.0, abs_tol=1e-9)


def test_build_scene_snapshot_marks_pickable_visual_objects() -> None:
    scene = build_scene_snapshot(profile=_profile(), snap=_snap(pan_deg=0.0, tilt_deg=0.0))
    assert scene is not None
    assert scene.frames[0].pickable is True
    assert scene.frames[0].object_id == "actual"
    assert scene.frames[0].object_kind == "pose_frame"
    assert scene.lines[0].pickable is True
    assert scene.lines[0].object_id == "actual_aim"
    assert scene.lines[0].object_kind == "aim_line"
    assert scene.debug_frames[0].pickable is True
    assert scene.debug_lines[0].pickable is True
