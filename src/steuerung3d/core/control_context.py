from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ControlContextMode = Literal["independent_axes", "sync_kinematic_jog", "goto_pose", "follow_path"]
ControlContextTargetKind = Literal["axis", "rig", "pose", "path"]
ControlContextInputMapping = Literal["axis_rate", "cartesian_xyz", "pose_speed", "path_speed_trim"]


@dataclass(frozen=True)
class ControlContext:
    type: Literal["control_context"] = "control_context"
    version: int = 1
    seq: int = 0
    mode: ControlContextMode = "independent_axes"
    selected_target_kind: ControlContextTargetKind = "axis"
    input_mapping: ControlContextInputMapping = "axis_rate"
    motion_enabled: bool = True
