from __future__ import annotations

from pathlib import Path

from steuerung3d.config.toml_loader import load_toml

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


def _axis_entries(raw: dict) -> list[dict]:
    axis_items = list(raw.get("axes", []) or [])
    if axis_items:
        return [dict(item or {}) for item in axis_items]
    pair_items = list(raw.get("pairs", []) or [])
    return [dict(item or {}) for item in pair_items]


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
    raw = dict(load_toml(Path(path)))
    sup = dict(raw.get("supervisor", {}) or {})
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
    launch = dict(raw.get("launch", {}) or {})
    profile = SupervisorProfile(
        supervisor_id=_as_str(sup.get("id", "supervisor")).strip() or "supervisor",
        title=_as_str(sup.get("title", sup.get("id", "Supervisor"))).strip() or "Supervisor",
        cycle_ms=max(20, _as_int(sup.get("cycle_ms", 50), 50)),
        telem_in=_as_str(sup.get("telem_in", "127.0.0.1:51002")).strip(),
        intent_out=_as_str(sup.get("intent_out", "127.0.0.1:51001")).strip(),
        gui=_as_bool(sup.get("gui"), True),
        stale_after_ms=max(200, _as_int(sup.get("stale_after_ms", 800), 800)),
        launch_stack=_as_str(launch.get("stack_profile", "")).strip(),
        axes=tuple(axes),
    )
    if not profile.axes:
        raise ValueError("supervisor profile must define at least one axis")
    return profile
