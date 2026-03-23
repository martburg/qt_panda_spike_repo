from __future__ import annotations

from dataclasses import dataclass, field

from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.rig.kinematics.two_axis_head import (
    TwoAxisHeadGeometry,
    TwoAxisHeadPose,
    aim_ray_end,
    forward_two_axis_head_pose,
    joint1_axis_world,
    joint2_axis_world,
    pose_from_telemetry,
)

from .types import FrameViz, LineViz


def _new_line_list() -> list[LineViz]:
    return []


def _new_frame_list() -> list[FrameViz]:
    return []


def _new_warning_list() -> list[str]:
    return []


@dataclass(frozen=True)
class SceneSnapshot:
    machine_id: str
    actual_pose: TwoAxisHeadPose | None = None
    target_pose: TwoAxisHeadPose | None = None
    frames: list[FrameViz] = field(default_factory=_new_frame_list)
    lines: list[LineViz] = field(default_factory=_new_line_list)
    debug_frames: list[FrameViz] = field(default_factory=_new_frame_list)
    debug_lines: list[LineViz] = field(default_factory=_new_line_list)
    warnings: list[str] = field(default_factory=_new_warning_list)


@dataclass(frozen=True)
class TwoAxisHeadTargetState:
    joint1_axis_pos_deg: float
    joint2_axis_pos_deg: float


def _add_vec3(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale_vec3(v: tuple[float, float, float], scale: float) -> tuple[float, float, float]:
    return (v[0] * scale, v[1] * scale, v[2] * scale)


def _build_debug_frames_and_lines(
    *,
    geometry: TwoAxisHeadGeometry,
    joint1_axis_pos_deg: float | None,
) -> tuple[list[FrameViz], list[LineViz]]:
    origin = geometry.base_origin_xyz
    line_length = float(geometry.aim_ray_length_m)
    joint1_dir = joint1_axis_world(geometry=geometry)
    joint2_dir = joint2_axis_world(
        geometry=geometry,
        joint1_axis_pos_deg=(0.0 if joint1_axis_pos_deg is None else float(joint1_axis_pos_deg)),
    )
    debug_frames = [
        FrameViz(
            name="base_hint",
            origin_xyz=origin,
            aim_dir_xyz=joint1_dir,
            object_id="base_hint",
            object_kind="debug_frame",
            pickable=True,
        ),
        FrameViz(
            name="joint1_hint",
            origin_xyz=origin,
            aim_dir_xyz=joint2_dir,
            object_id="joint1_hint",
            object_kind="debug_frame",
            pickable=True,
        ),
    ]
    debug_lines = [
        LineViz(
            name="joint1_axis_base",
            start_xyz=origin,
            end_xyz=_add_vec3(origin, _scale_vec3(joint1_dir, line_length)),
            object_id="joint1_axis_base",
            object_kind="debug_line",
            pickable=True,
        ),
        LineViz(
            name="joint2_axis_current",
            start_xyz=origin,
            end_xyz=_add_vec3(origin, _scale_vec3(joint2_dir, line_length)),
            object_id="joint2_axis_current",
            object_kind="debug_line",
            pickable=True,
        ),
    ]
    return debug_frames, debug_lines


def build_two_axis_head_scene_snapshot(
    *,
    geometry: TwoAxisHeadGeometry,
    snap: TelemetrySnapshot,
    target: TwoAxisHeadTargetState | None = None,
) -> SceneSnapshot:
    actual_pose = pose_from_telemetry(geometry=geometry, snap=snap)
    target_pose = None
    if target is not None:
        target_pose = forward_two_axis_head_pose(
            geometry=geometry,
            joint1_axis_pos_deg=float(target.joint1_axis_pos_deg),
            joint2_axis_pos_deg=float(target.joint2_axis_pos_deg),
        )

    frames: list[FrameViz] = []
    lines: list[LineViz] = []
    warnings: list[str] = []

    if actual_pose is None:
        warnings.append(
            f"missing_two_axis_head_axes:{geometry.joint1_axis_id},{geometry.joint2_axis_id}"
        )
    else:
        frames.append(
            FrameViz(
                name="actual",
                origin_xyz=actual_pose.tool_origin_xyz,
                aim_dir_xyz=actual_pose.aim_dir_xyz,
                object_id="actual",
                object_kind="pose_frame",
                pickable=True,
            )
        )
        lines.append(
            LineViz(
                name="actual_aim",
                start_xyz=actual_pose.tool_origin_xyz,
                end_xyz=aim_ray_end(pose=actual_pose, length_m=float(geometry.aim_ray_length_m)),
                object_id="actual_aim",
                object_kind="aim_line",
                pickable=True,
            )
        )

    if target_pose is not None:
        frames.append(
            FrameViz(
                name="target",
                origin_xyz=target_pose.tool_origin_xyz,
                aim_dir_xyz=target_pose.aim_dir_xyz,
                object_id="target",
                object_kind="pose_frame",
                pickable=True,
            )
        )
        lines.append(
            LineViz(
                name="target_aim",
                start_xyz=target_pose.tool_origin_xyz,
                end_xyz=aim_ray_end(pose=target_pose, length_m=float(geometry.aim_ray_length_m)),
                object_id="target_aim",
                object_kind="aim_line",
                pickable=True,
            )
        )

    debug_frames, debug_lines = _build_debug_frames_and_lines(
        geometry=geometry,
        joint1_axis_pos_deg=(None if actual_pose is None else actual_pose.joint1_deg),
    )

    return SceneSnapshot(
        machine_id=str(geometry.machine_id),
        actual_pose=actual_pose,
        target_pose=target_pose,
        frames=frames,
        lines=lines,
        debug_frames=debug_frames,
        debug_lines=debug_lines,
        warnings=warnings,
    )
