from __future__ import annotations

from dataclasses import dataclass

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class RawPickResult:
    object_name: str
    machine_id: str = ""
    object_id: str = ""
    object_kind: str = ""
    hit_point_world: Vec3 | None = None


@dataclass(frozen=True)
class ViewportSelectionEvent:
    object_name: str
    machine_id: str = ""
    object_id: str = ""
    object_kind: str = ""
    hit_point_world: Vec3 | None = None


@dataclass(frozen=True)
class ShellSelectionState:
    selected_object_name: str = ""
    selected_machine_id: str = ""
    selected_object_id: str = ""
    selected_object_kind: str = ""
    summary_text: str = "No viewport selection"


def normalize_viewport_object_name(raw_name: str) -> str:
    return str(raw_name or "").strip()


def selection_event_from_pick_result(
    pick: RawPickResult | None,
) -> ViewportSelectionEvent | None:
    if pick is None:
        return None
    object_name = normalize_viewport_object_name(pick.object_name)
    if not object_name:
        return None
    return ViewportSelectionEvent(
        object_name=object_name,
        machine_id=str(pick.machine_id or "").strip(),
        object_id=str(pick.object_id or "").strip(),
        object_kind=str(pick.object_kind or "").strip(),
        hit_point_world=pick.hit_point_world,
    )


def selection_summary_from_event(event: ViewportSelectionEvent | None) -> ShellSelectionState:
    if event is None:
        return ShellSelectionState()
    object_name = normalize_viewport_object_name(event.object_name)
    if not object_name:
        return ShellSelectionState()
    machine_id = str(event.machine_id or "").strip()
    object_id = str(event.object_id or "").strip()
    object_kind = str(event.object_kind or "").strip()
    prefix = f"{machine_id} | " if machine_id else ""
    return ShellSelectionState(
        selected_object_name=object_name,
        selected_machine_id=machine_id,
        selected_object_id=object_id,
        selected_object_kind=object_kind,
        summary_text=f"{prefix}{object_name}",
    )
