from __future__ import annotations

from dataclasses import dataclass

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class FrameViz:
    name: str
    origin_xyz: Vec3
    aim_dir_xyz: Vec3
    object_id: str = ""
    object_kind: str = ""
    pickable: bool = False


@dataclass(frozen=True)
class LineViz:
    name: str
    start_xyz: Vec3
    end_xyz: Vec3
    object_id: str = ""
    object_kind: str = ""
    pickable: bool = False
