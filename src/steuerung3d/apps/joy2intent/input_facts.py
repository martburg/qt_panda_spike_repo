from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from steuerung3d.core.control_context import ControlContext
from steuerung3d.core.joy_state import clamp_soll_speed

from .axis_math import apply_deadzone_only
from .mapping_types import JoyInputFacts, _JoyBindingsLike, _JoyReportLike


def pressed_buttons(rc: Any) -> set[int]:
    if hasattr(rc, "pressed"):
        try:
            return set(rc.pressed)
        except Exception:
            return set()
    if hasattr(rc, "buttons"):
        try:
            return {i for i, v in enumerate(rc.buttons) if v}
        except Exception:
            return set()
    return set()


def button_aliases(value: int | Sequence[int] | None) -> set[int]:
    if value is None:
        return set()
    if isinstance(value, int):
        return {value}
    out: set[int] = set()
    for item in value:
        out.add(item)
    return out


def select_aliases(entry: int | Sequence[int]) -> set[int]:
    if isinstance(entry, int):
        return {entry}
    out: set[int] = set()
    for item in entry:
        out.add(item)
    return out


def axes_list(rc: Any) -> list[float]:
    if hasattr(rc, "axes"):
        try:
            return list(rc.axes)
        except Exception:
            return []
    return []


def selected_winch_ids(
    *, select_buttons: Sequence[int | Sequence[int]], pressed: set[int], rig_ids: Sequence[str]
) -> set[str]:
    selected: list[str] = []
    for i, entry in enumerate(select_buttons or []):
        aliases = select_aliases(entry)
        if aliases & pressed and i < len(rig_ids):
            selected.append(str(rig_ids[i]))
    return set(selected)


def collect_input_facts(
    *,
    rc: _JoyReportLike,
    bind: _JoyBindingsLike,
    rig_ids: Sequence[str],
    control_context: ControlContext | None,
) -> JoyInputFacts:
    deadman_btn = button_aliases(bind.buttons.get("deadman"))
    fine_btn = button_aliases(bind.buttons.get("fine"))
    pressed = pressed_buttons(rc)
    axes = axes_list(rc)

    deadman = bool(deadman_btn & pressed)
    fine = bool(fine_btn & pressed)

    soll_speed = 0.0
    soll_axis = bind.axes.get("soll_speed")
    if soll_axis is not None and 0 <= soll_axis < len(axes):
        soll_speed = float(axes[soll_axis])
        if bind.invert.get("soll_speed", False):
            soll_speed = -soll_speed
        soll_speed = apply_deadzone_only(soll_speed, bind.deadzone)
    soll_speed = clamp_soll_speed(soll_speed)

    use_contextual_local_manual = bool(
        control_context is not None
        and str(getattr(control_context, "mode", "")) == "independent_axes"
        and str(getattr(control_context, "input_mapping", "")) == "axis_rate"
    )
    motion_enabled = bool(getattr(control_context, "motion_enabled", True))

    return JoyInputFacts(
        pressed=pressed,
        axes=axes,
        deadman=deadman,
        fine=fine,
        soll_speed=float(soll_speed),
        selected_set=selected_winch_ids(
            select_buttons=bind.select_buttons or [],
            pressed=pressed,
            rig_ids=rig_ids,
        ),
        rig_ids=list(rig_ids),
        use_contextual_local_manual=use_contextual_local_manual,
        motion_enabled=motion_enabled,
    )
