from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import cos, radians, sin, sqrt

from steuerung3d.core.telemetry import TelemetrySnapshot

Vec3 = tuple[float, float, float]


def _vec3() -> Vec3:
    return (0.0, 0.0, 0.0)


def _empty_clipped_axes() -> dict[str, float]:
    return {}


def _default_joint1_axis_base_xyz() -> Vec3:
    return (0.0, 0.0, 1.0)


def _default_joint2_axis_joint1_xyz() -> Vec3:
    return (0.0, 1.0, 0.0)


def _default_tool_forward_xyz() -> Vec3:
    return (1.0, 0.0, 0.0)


def _add_vec3(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale_vec3(v: Vec3, scale: float) -> Vec3:
    return (v[0] * scale, v[1] * scale, v[2] * scale)


def _dot_vec3(a: Vec3, b: Vec3) -> float:
    return (a[0] * b[0]) + (a[1] * b[1]) + (a[2] * b[2])


def _cross_vec3(a: Vec3, b: Vec3) -> Vec3:
    return (
        (a[1] * b[2]) - (a[2] * b[1]),
        (a[2] * b[0]) - (a[0] * b[2]),
        (a[0] * b[1]) - (a[1] * b[0]),
    )


def _normalize_vec3(v: Vec3, *, fallback: Vec3) -> Vec3:
    norm = sqrt((v[0] * v[0]) + (v[1] * v[1]) + (v[2] * v[2]))
    if norm <= 1e-12:
        return fallback
    inv = 1.0 / norm
    return (v[0] * inv, v[1] * inv, v[2] * inv)


def _rotate_vec3_about_axis(*, v: Vec3, axis_xyz: Vec3, angle_deg: float) -> Vec3:
    axis = _normalize_vec3(v=axis_xyz, fallback=_default_joint1_axis_base_xyz())
    angle_rad = radians(float(angle_deg))
    c = cos(angle_rad)
    s = sin(angle_rad)
    term1 = _scale_vec3(v, c)
    term2 = _scale_vec3(_cross_vec3(axis, v), s)
    term3 = _scale_vec3(axis, _dot_vec3(axis, v) * (1.0 - c))
    return _add_vec3(_add_vec3(term1, term2), term3)


def _rotate_two_axis_head(
    *,
    geometry: TwoAxisHeadGeometry,
    joint1_deg: float,
    joint2_deg: float,
    v: Vec3,
) -> Vec3:
    """Rotate a vector through the practical-first two-axis-head chain.

    Geometry conventions:
    - `joint1_axis_base_xyz` is expressed in the base frame.
    - `joint2_axis_joint1_xyz` is expressed in the frame after joint1.
    - `tool_forward_xyz` and `tool_offset_xyz` are expressed in the tool/joint2 local frame.

    This remains a simple 2-DOF head model, but it no longer assumes that
    joint1 must be a vertical pan axis.
    """

    after_joint2 = _rotate_vec3_about_axis(
        v=v,
        axis_xyz=_normalize_vec3(
            geometry.joint2_axis_joint1_xyz,
            fallback=_default_joint2_axis_joint1_xyz(),
        ),
        angle_deg=joint2_deg,
    )
    return _rotate_vec3_about_axis(
        v=after_joint2,
        axis_xyz=_normalize_vec3(
            geometry.joint1_axis_base_xyz,
            fallback=_default_joint1_axis_base_xyz(),
        ),
        angle_deg=joint1_deg,
    )


@dataclass(frozen=True)
class TwoAxisHeadGeometry:
    machine_id: str
    joint1_axis_id: str
    joint2_axis_id: str
    joint1_sign: float = 1.0
    joint2_sign: float = 1.0
    joint1_zero_deg: float = 0.0
    joint2_zero_deg: float = 0.0
    joint1_min_deg: float = -180.0
    joint1_max_deg: float = 180.0
    joint2_min_deg: float = -90.0
    joint2_max_deg: float = 90.0
    joint1_max_rate_deg_s: float = 30.0
    joint2_max_rate_deg_s: float = 30.0
    joint1_axis_base_xyz: Vec3 = field(default_factory=_default_joint1_axis_base_xyz)
    joint2_axis_joint1_xyz: Vec3 = field(default_factory=_default_joint2_axis_joint1_xyz)
    tool_forward_xyz: Vec3 = field(default_factory=_default_tool_forward_xyz)
    base_origin_xyz: Vec3 = field(default_factory=_vec3)
    tool_offset_xyz: Vec3 = field(default_factory=_vec3)
    aim_ray_length_m: float = 1.0

    def axis_ids(self) -> tuple[str, str]:
        return (str(self.joint1_axis_id), str(self.joint2_axis_id))

    def logical_joint1_deg(self, raw_axis_pos_deg: float) -> float:
        return float(self.joint1_sign) * (float(raw_axis_pos_deg) - float(self.joint1_zero_deg))

    def logical_joint2_deg(self, raw_axis_pos_deg: float) -> float:
        return float(self.joint2_sign) * (float(raw_axis_pos_deg) - float(self.joint2_zero_deg))

    def clamp_joint1_deg(self, logical_joint1_deg: float) -> float:
        return min(
            float(self.joint1_max_deg), max(float(self.joint1_min_deg), float(logical_joint1_deg))
        )

    def clamp_joint2_deg(self, logical_joint2_deg: float) -> float:
        return min(
            float(self.joint2_max_deg), max(float(self.joint2_min_deg), float(logical_joint2_deg))
        )

    @property
    def pan_axis_id(self) -> str:
        return self.joint1_axis_id

    @property
    def tilt_axis_id(self) -> str:
        return self.joint2_axis_id

    @property
    def pan_sign(self) -> float:
        return self.joint1_sign

    @property
    def tilt_sign(self) -> float:
        return self.joint2_sign

    @property
    def pan_zero_deg(self) -> float:
        return self.joint1_zero_deg

    @property
    def tilt_zero_deg(self) -> float:
        return self.joint2_zero_deg

    @property
    def pan_min_deg(self) -> float:
        return self.joint1_min_deg

    @property
    def pan_max_deg(self) -> float:
        return self.joint1_max_deg

    @property
    def tilt_min_deg(self) -> float:
        return self.joint2_min_deg

    @property
    def tilt_max_deg(self) -> float:
        return self.joint2_max_deg

    @property
    def pan_max_rate_deg_s(self) -> float:
        return self.joint1_max_rate_deg_s

    @property
    def tilt_max_rate_deg_s(self) -> float:
        return self.joint2_max_rate_deg_s


def joint1_axis_world(*, geometry: TwoAxisHeadGeometry) -> Vec3:
    return _normalize_vec3(
        geometry.joint1_axis_base_xyz,
        fallback=_default_joint1_axis_base_xyz(),
    )


def joint2_axis_world(*, geometry: TwoAxisHeadGeometry, joint1_axis_pos_deg: float) -> Vec3:
    joint1_deg = geometry.clamp_joint1_deg(geometry.logical_joint1_deg(joint1_axis_pos_deg))
    joint2_axis_joint1 = _normalize_vec3(
        geometry.joint2_axis_joint1_xyz,
        fallback=_default_joint2_axis_joint1_xyz(),
    )
    return _rotate_vec3_about_axis(
        v=joint2_axis_joint1,
        axis_xyz=joint1_axis_world(geometry=geometry),
        angle_deg=joint1_deg,
    )


@dataclass(frozen=True)
class TwoAxisHeadControlMap:
    joint1_channel: str = "look_pan"
    joint2_channel: str = "look_tilt"


@dataclass(frozen=True)
class TwoAxisHeadPose:
    joint1_deg: float
    joint2_deg: float
    tool_origin_xyz: Vec3
    aim_dir_xyz: Vec3

    @property
    def pan_deg(self) -> float:
        return self.joint1_deg

    @property
    def tilt_deg(self) -> float:
        return self.joint2_deg


@dataclass(frozen=True)
class TwoAxisHeadManualIntent:
    look_pan_rate_norm: float = 0.0
    look_tilt_rate_norm: float = 0.0
    enable_motion: bool = False
    actor_id: str = ""

    @property
    def pan_rate_norm(self) -> float:
        return self.look_pan_rate_norm

    @property
    def tilt_rate_norm(self) -> float:
        return self.look_tilt_rate_norm


@dataclass(frozen=True)
class AxisVelocityDemand:
    axis_id: str
    vel: float


@dataclass(frozen=True)
class ConstraintReport:
    ok: bool
    warnings: tuple[str, ...] = ()
    clipped_axes: Mapping[str, float] = field(default_factory=_empty_clipped_axes)


@dataclass(frozen=True)
class TwoAxisHeadAxisDemand:
    demands: tuple[AxisVelocityDemand, ...]
    constraints: ConstraintReport


def forward_two_axis_head_pose(
    *, geometry: TwoAxisHeadGeometry, joint1_axis_pos_deg: float, joint2_axis_pos_deg: float
) -> TwoAxisHeadPose:
    joint1_deg = geometry.clamp_joint1_deg(geometry.logical_joint1_deg(joint1_axis_pos_deg))
    joint2_deg = geometry.clamp_joint2_deg(geometry.logical_joint2_deg(joint2_axis_pos_deg))
    aim_dir = _rotate_two_axis_head(
        geometry=geometry,
        joint1_deg=joint1_deg,
        joint2_deg=joint2_deg,
        v=(
            float(geometry.tool_forward_xyz[0]),
            float(geometry.tool_forward_xyz[1]),
            float(geometry.tool_forward_xyz[2]),
        ),
    )
    tool_offset = _rotate_two_axis_head(
        geometry=geometry,
        joint1_deg=joint1_deg,
        joint2_deg=joint2_deg,
        v=(
            float(geometry.tool_offset_xyz[0]),
            float(geometry.tool_offset_xyz[1]),
            float(geometry.tool_offset_xyz[2]),
        ),
    )
    tool_origin = _add_vec3(
        (
            float(geometry.base_origin_xyz[0]),
            float(geometry.base_origin_xyz[1]),
            float(geometry.base_origin_xyz[2]),
        ),
        tool_offset,
    )
    return TwoAxisHeadPose(
        joint1_deg=float(joint1_deg),
        joint2_deg=float(joint2_deg),
        tool_origin_xyz=tool_origin,
        aim_dir_xyz=aim_dir,
    )


def pose_from_telemetry(
    *, geometry: TwoAxisHeadGeometry, snap: TelemetrySnapshot
) -> TwoAxisHeadPose | None:
    joint1_axis = snap.axes.get(str(geometry.joint1_axis_id))
    joint2_axis = snap.axes.get(str(geometry.joint2_axis_id))
    if joint1_axis is None or joint2_axis is None:
        return None
    return forward_two_axis_head_pose(
        geometry=geometry,
        joint1_axis_pos_deg=float(joint1_axis.pos),
        joint2_axis_pos_deg=float(joint2_axis.pos),
    )


def build_two_axis_head_axis_demand(
    *,
    geometry: TwoAxisHeadGeometry,
    intent: TwoAxisHeadManualIntent,
    snap: TelemetrySnapshot | None = None,
) -> TwoAxisHeadAxisDemand:
    warnings: list[str] = []
    clipped_axes: dict[str, float] = {}
    if not intent.enable_motion:
        return TwoAxisHeadAxisDemand(
            demands=(
                AxisVelocityDemand(axis_id=str(geometry.joint1_axis_id), vel=0.0),
                AxisVelocityDemand(axis_id=str(geometry.joint2_axis_id), vel=0.0),
            ),
            constraints=ConstraintReport(ok=True),
        )

    joint1_rate_norm = max(-1.0, min(1.0, float(intent.look_pan_rate_norm)))
    joint2_rate_norm = max(-1.0, min(1.0, float(intent.look_tilt_rate_norm)))
    joint1_vel = (
        joint1_rate_norm * float(geometry.joint1_max_rate_deg_s) * float(geometry.joint1_sign)
    )
    joint2_vel = (
        joint2_rate_norm * float(geometry.joint2_max_rate_deg_s) * float(geometry.joint2_sign)
    )

    if snap is not None:
        joint1_axis = snap.axes.get(str(geometry.joint1_axis_id))
        joint2_axis = snap.axes.get(str(geometry.joint2_axis_id))
        if joint1_axis is not None:
            joint1_deg = geometry.logical_joint1_deg(float(joint1_axis.pos))
            if joint1_deg <= float(geometry.joint1_min_deg) and joint1_vel < 0.0:
                joint1_vel = 0.0
                clipped_axes[str(geometry.joint1_axis_id)] = float(geometry.joint1_min_deg)
                warnings.append(f"joint1_min_reached:{geometry.joint1_axis_id}")
            elif joint1_deg >= float(geometry.joint1_max_deg) and joint1_vel > 0.0:
                joint1_vel = 0.0
                clipped_axes[str(geometry.joint1_axis_id)] = float(geometry.joint1_max_deg)
                warnings.append(f"joint1_max_reached:{geometry.joint1_axis_id}")
        if joint2_axis is not None:
            joint2_deg = geometry.logical_joint2_deg(float(joint2_axis.pos))
            if joint2_deg <= float(geometry.joint2_min_deg) and joint2_vel < 0.0:
                joint2_vel = 0.0
                clipped_axes[str(geometry.joint2_axis_id)] = float(geometry.joint2_min_deg)
                warnings.append(f"joint2_min_reached:{geometry.joint2_axis_id}")
            elif joint2_deg >= float(geometry.joint2_max_deg) and joint2_vel > 0.0:
                joint2_vel = 0.0
                clipped_axes[str(geometry.joint2_axis_id)] = float(geometry.joint2_max_deg)
                warnings.append(f"joint2_max_reached:{geometry.joint2_axis_id}")

    return TwoAxisHeadAxisDemand(
        demands=(
            AxisVelocityDemand(axis_id=str(geometry.joint1_axis_id), vel=float(joint1_vel)),
            AxisVelocityDemand(axis_id=str(geometry.joint2_axis_id), vel=float(joint2_vel)),
        ),
        constraints=ConstraintReport(
            ok=(not warnings), warnings=tuple(warnings), clipped_axes=clipped_axes
        ),
    )


def aim_ray_end(*, pose: TwoAxisHeadPose, length_m: float) -> Vec3:
    return _add_vec3(pose.tool_origin_xyz, _scale_vec3(pose.aim_dir_xyz, float(length_m)))
