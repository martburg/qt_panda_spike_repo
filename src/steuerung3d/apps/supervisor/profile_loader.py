from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from steuerung3d.config.toml_loader import load_toml
from steuerung3d.rig.kinematics.two_axis_head import TwoAxisHeadControlMap, TwoAxisHeadGeometry

from .models import AxisConfig, SupervisorProfile


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except Exception:
            return int(default)
    return int(default)


def _as_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _as_table(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(k): v for k, v in mapping.items()}


def _as_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except Exception:
            return float(default)
    return float(default)


def _as_vec3(
    value: object, default: tuple[float, float, float] = (0.0, 0.0, 0.0)
) -> tuple[float, float, float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return default
    values = list(cast(Sequence[object], value))
    if len(values) != 3:
        return default
    return (
        _as_float(values[0], default[0]),
        _as_float(values[1], default[1]),
        _as_float(values[2], default[2]),
    )


def _as_object_list(value: object) -> list[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(cast(Sequence[object], value))


def _axis_entries(raw: Mapping[str, object]) -> list[dict[str, object]]:
    axis_items = _as_object_list(raw.get("axes", []))
    if axis_items:
        return [_as_table(item) for item in axis_items]
    pair_items = _as_object_list(raw.get("pairs", []))
    return [_as_table(item) for item in pair_items]


def _two_axis_head_table(raw: Mapping[str, object]) -> dict[str, object]:
    direct = _as_table(raw.get("two_axis_head", {}))
    if direct:
        return direct
    if _as_table(raw.get("pan_tilt", {})):
        raise ValueError(
            "pan_tilt aliases were removed; use two_axis_head with joint1/joint2 names"
        )

    kin = _as_table(raw.get("kinematics", {}))
    kind = _as_str(kin.get("kind", "")).strip()

    table = _as_table(kin.get("two_axis_head", {}))
    if table:
        return table
    if _as_table(kin.get("pan_tilt", {})):
        raise ValueError(
            "pan_tilt aliases were removed; use two_axis_head with joint1/joint2 names"
        )

    if kind == "two_axis_head":
        axes = _as_table(kin.get("axes", {}))
        merged = dict(kin)
        merged.pop("axes", None)
        merged.pop("control_map", None)
        merged.pop("kind", None)
        merged.pop("two_axis_head", None)
        for key, value in axes.items():
            merged[key] = value
        return merged
    return {}


def _load_kinematics_control_map(raw: Mapping[str, object]) -> TwoAxisHeadControlMap | None:
    table = _two_axis_head_table(raw)
    if not table:
        return None

    kin = _as_table(raw.get("kinematics", {}))
    control_map = _as_table(kin.get("control_map", {}))
    joint1_channel = _as_str(control_map.get("joint1", "look_pan")).strip() or "look_pan"
    joint2_channel = _as_str(control_map.get("joint2", "look_tilt")).strip() or "look_tilt"
    return TwoAxisHeadControlMap(joint1_channel=joint1_channel, joint2_channel=joint2_channel)


def _load_kinematics_geometry(
    raw: Mapping[str, object], *, default_machine_id: str
) -> TwoAxisHeadGeometry | None:
    table = _two_axis_head_table(raw)
    if not table:
        return None

    machine_id = _as_str(table.get("machine_id", default_machine_id)).strip() or default_machine_id
    joint1_axis_id = _as_str(table.get("joint1_axis_id", "")).strip()
    joint2_axis_id = _as_str(table.get("joint2_axis_id", "")).strip()
    if not joint1_axis_id or not joint2_axis_id:
        raise ValueError("two_axis_head config requires joint1_axis_id and joint2_axis_id")

    return TwoAxisHeadGeometry(
        machine_id=machine_id,
        joint1_axis_id=joint1_axis_id,
        joint2_axis_id=joint2_axis_id,
        joint1_sign=_as_float(table.get("joint1_sign", 1.0), 1.0),
        joint2_sign=_as_float(table.get("joint2_sign", 1.0), 1.0),
        joint1_zero_deg=_as_float(table.get("joint1_zero_deg", 0.0), 0.0),
        joint2_zero_deg=_as_float(table.get("joint2_zero_deg", 0.0), 0.0),
        joint1_min_deg=_as_float(table.get("joint1_min_deg", -180.0), -180.0),
        joint1_max_deg=_as_float(table.get("joint1_max_deg", 180.0), 180.0),
        joint2_min_deg=_as_float(table.get("joint2_min_deg", -90.0), -90.0),
        joint2_max_deg=_as_float(table.get("joint2_max_deg", 90.0), 90.0),
        joint1_max_rate_deg_s=_as_float(table.get("joint1_max_rate_deg_s", 30.0), 30.0),
        joint2_max_rate_deg_s=_as_float(table.get("joint2_max_rate_deg_s", 30.0), 30.0),
        joint1_axis_base_xyz=_as_vec3(table.get("joint1_axis_base_xyz"), (0.0, 0.0, 1.0)),
        joint2_axis_joint1_xyz=_as_vec3(table.get("joint2_axis_joint1_xyz"), (0.0, 1.0, 0.0)),
        tool_forward_xyz=_as_vec3(table.get("tool_forward_xyz"), (1.0, 0.0, 0.0)),
        base_origin_xyz=_as_vec3(table.get("base_origin_xyz")),
        tool_offset_xyz=_as_vec3(table.get("tool_offset_xyz")),
        aim_ray_length_m=_as_float(table.get("aim_ray_length_m", 1.0), 1.0),
    )


def _normalize_axis_entry(entry: dict[str, object]) -> AxisConfig:
    unit_id = _as_str(entry.get("unit_id", entry.get("pair_id", entry.get("axis_id", "")))).strip()
    axis_id = _as_str(entry.get("axis_id", unit_id)).strip()
    densi_id = _as_str(entry.get("densi_id", axis_id)).strip()
    hip_id = _as_str(entry.get("hip_id", f"hip_{unit_id or axis_id}")).strip()
    if not unit_id or not axis_id:
        raise ValueError(f"invalid axis entry: {entry!r}")
    return AxisConfig(
        unit_id=unit_id,
        axis_id=axis_id,
        densi_id=densi_id,
        hip_id=hip_id,
        selected=_as_bool(entry.get("selected"), True),
        densi_action_out=_as_str(entry.get("densi_action_out", "")).strip(),
        hip_launch=_as_str(entry.get("hip_launch", "")).strip(),
        densi_launch=_as_str(entry.get("densi_launch", "")).strip(),
    )


def load_profile(path: str | Path) -> SupervisorProfile:
    raw = load_toml(Path(path))
    sup = _as_table(raw.get("supervisor", {}))
    axis_items = _axis_entries(raw)
    axes: list[AxisConfig] = []
    seen_unit_ids: set[str] = set()
    seen_axis_ids: set[str] = set()
    for entry in axis_items:
        axis = _normalize_axis_entry(entry)
        if axis.unit_id in seen_unit_ids:
            raise ValueError(f"duplicate supervisor unit_id: {axis.unit_id}")
        if axis.axis_id in seen_axis_ids:
            raise ValueError(f"duplicate supervisor axis_id: {axis.axis_id}")
        seen_unit_ids.add(axis.unit_id)
        seen_axis_ids.add(axis.axis_id)
        axes.append(axis)
    launch = _as_table(raw.get("launch", {}))
    supervisor_id = _as_str(sup.get("id", "supervisor")).strip() or "supervisor"
    kinematics = _load_kinematics_geometry(raw, default_machine_id=supervisor_id)
    kinematics_control_map = _load_kinematics_control_map(raw)
    profile = SupervisorProfile(
        supervisor_id=supervisor_id,
        title=_as_str(sup.get("title", sup.get("id", "Supervisor"))).strip() or "Supervisor",
        cycle_ms=max(20, _as_int(sup.get("cycle_ms", 50), 50)),
        telem_in=_as_str(sup.get("telem_in", "127.0.0.1:51002")).strip(),
        intent_out=_as_str(sup.get("intent_out", "127.0.0.1:51001")).strip(),
        gui=_as_bool(sup.get("gui"), True),
        stale_after_ms=max(200, _as_int(sup.get("stale_after_ms", 800), 800)),
        launch_stack=_as_str(launch.get("stack_profile", "")).strip(),
        axes=tuple(axes),
        kinematics=kinematics,
        kinematics_control_map=kinematics_control_map,
    )
    if not profile.axes:
        raise ValueError("supervisor profile must define at least one axis")
    return profile
