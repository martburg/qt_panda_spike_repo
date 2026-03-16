from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from steuerung3d.core.control_context import ControlContext
from steuerung3d.core.intents import (
    ClaimAxis,
    EnableAxis,
    JogWinch,
    JoyStateUpdate,
    LocalAxisManualRequest,
)
from steuerung3d.core.joy_state import clamp_soll_speed


class _JoyBindingsLike(Protocol):
    @property
    def axes(self) -> Mapping[str, int]: ...

    @property
    def buttons(self) -> Mapping[str, int | Sequence[int]]: ...

    @property
    def deadzone(self) -> float: ...

    @property
    def expo(self) -> float: ...

    @property
    def select_buttons(self) -> Sequence[int | Sequence[int]]: ...

    @property
    def invert(self) -> Mapping[str, bool]: ...


class _JoyLimitsLike(Protocol):
    @property
    def fine_scale(self) -> float: ...

    def max_speed(self) -> float: ...


class _IndexedJoyStateLike(Protocol):
    prev_deadman: bool
    deadman_prev: bool
    prev_active_winch_idxs: set[int]
    enabled_winch_ids: set[str]


class _NamedJoyStateLike(Protocol):
    prev_deadman: bool
    deadman_prev: bool
    prev_active_winch_idxs: set[int]
    enabled_winch_ids: set[str]


_JoyStateLike = _IndexedJoyStateLike | _NamedJoyStateLike


class _JoyReportLike(Protocol):
    @property
    def axes(self) -> Sequence[float]: ...

    @property
    def buttons(self) -> Sequence[int]: ...


@dataclass(frozen=True)
class JoyInputFacts:
    pressed: set[int]
    axes: list[float]
    deadman: bool
    fine: bool
    soll_speed: float
    selected_set: set[str]
    rig_ids: list[str]
    use_contextual_local_manual: bool
    motion_enabled: bool


@dataclass(frozen=True)
class PreviousActivity:
    prev_deadman: bool
    active_ids: set[str]


@dataclass(frozen=True)
class RateFacts:
    rate: float


@dataclass(frozen=True)
class ActiveSelection:
    selected_ids: set[str]


def apply_deadzone_and_expo(x: float, deadzone: float, expo: float) -> float:
    if deadzone < 0:
        deadzone = 0.0
    if deadzone > 0.95:
        deadzone = 0.95

    ax = abs(x)
    if ax <= deadzone:
        return 0.0

    y = (ax - deadzone) / (1.0 - deadzone)
    if expo <= 0:
        expo = 1.0
    y = y**expo
    return y if x >= 0 else -y


def apply_deadzone_only(x: float, deadzone: float) -> float:
    if deadzone < 0:
        deadzone = 0.0
    if deadzone > 0.95:
        deadzone = 0.95
    if abs(x) <= deadzone:
        return 0.0
    return x


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
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for item in value:
            if isinstance(item, int):
                out.add(item)
    return out


def select_aliases(entry: int | Sequence[int]) -> set[int]:
    if isinstance(entry, int):
        return {entry}
    out: set[int] = set()
    if isinstance(entry, Sequence) and not isinstance(entry, str | bytes):
        for item in entry:
            if isinstance(item, int):
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


def build_joy_state_update(
    facts: JoyInputFacts, *, publish_selected_axes: bool = True
) -> JoyStateUpdate:
    selected_axes = tuple(sorted(facts.selected_set)) if publish_selected_axes else ()
    return JoyStateUpdate(
        deadman=bool(facts.deadman),
        select_hip=bool(selected_axes),
        soll_speed=float(facts.soll_speed),
        selected_axes=selected_axes,
    )


def previous_activity(*, st: _JoyStateLike, rig_ids: Sequence[str]) -> PreviousActivity:
    prev_deadman = bool(getattr(st, "prev_deadman", getattr(st, "deadman_prev", False)))
    prev_active = set(
        getattr(st, "prev_active_winch_idxs", getattr(st, "enabled_winch_ids", set()))
    )
    active_ids: set[str] = set()
    if prev_active and all(isinstance(x, int) for x in prev_active):
        active_ids = {str(rig_ids[i]) for i in prev_active if 0 <= i < len(rig_ids)}
    else:
        active_ids = {str(x) for x in prev_active}
    return PreviousActivity(prev_deadman=prev_deadman, active_ids=active_ids)


def update_state_active_selection(
    *, st: _JoyStateLike, selected_set: set[str], rig_ids: Sequence[str], deadman: bool
) -> None:
    if hasattr(st, "prev_active_winch_idxs"):
        st.prev_active_winch_idxs = {rig_ids.index(w) for w in selected_set if w in rig_ids}
    elif hasattr(st, "enabled_winch_ids"):
        st.enabled_winch_ids = set(selected_set)
    if hasattr(st, "prev_deadman"):
        st.prev_deadman = bool(deadman)
    else:
        st.deadman_prev = bool(deadman)


def clear_active_selection_state(st: _JoyStateLike) -> None:
    if hasattr(st, "prev_active_winch_idxs"):
        st.prev_active_winch_idxs.clear()
    elif hasattr(st, "enabled_winch_ids"):
        st.enabled_winch_ids.clear()
    if hasattr(st, "prev_deadman"):
        st.prev_deadman = False
    else:
        st.deadman_prev = False


def build_release_intents(
    *,
    active_ids: set[str],
    hip_id: str,
    use_contextual_local_manual: bool,
) -> list[object]:
    intents: list[object] = []
    if use_contextual_local_manual:
        intents.append(
            LocalAxisManualRequest(axis_ids=tuple(sorted(active_ids)), enable=False, rate=0.0)
        )
    else:
        for wid in sorted(active_ids):
            intents.append(EnableAxis(axis_id=wid, enable=False, hip_id=hip_id))
    return intents


def build_active_enable_intents(
    *, selected_set: set[str], current_active: set[str], hip_id: str
) -> list[object]:
    intents: list[object] = []
    for wid in sorted(selected_set):
        if wid not in current_active:
            intents.append(ClaimAxis(axis_id=wid, hip_id=hip_id))
        intents.append(EnableAxis(axis_id=wid, enable=True, hip_id=hip_id))
    return intents


def compute_manual_rate(
    *, axes: Sequence[float], bind: _JoyBindingsLike, lim: _JoyLimitsLike, fine: bool
) -> float:
    axis_idx = bind.axes.get("manual_jog")
    raw = 0.0
    if axis_idx is not None and 0 <= axis_idx < len(axes):
        raw = float(axes[axis_idx])
    if bind.invert.get("manual_jog", False):
        raw = -raw

    shaped = apply_deadzone_and_expo(raw, bind.deadzone, bind.expo)
    rate = shaped * lim.max_speed()
    if fine:
        rate *= float(lim.fine_scale)
    return float(rate)


def build_motion_intents(
    *,
    selected_set: set[str],
    hip_id: str,
    use_contextual_local_manual: bool,
    deadman: bool,
    rate: float,
) -> list[object]:
    intents: list[object] = []
    if use_contextual_local_manual:
        intents.append(
            LocalAxisManualRequest(
                axis_ids=tuple(sorted(selected_set)),
                enable=bool(deadman),
                rate=float(rate),
            )
        )
    elif rate != 0.0:
        for wid in sorted(selected_set):
            intents.append(JogWinch(winch_id=wid, rate=float(rate), hip_id=hip_id))
    return intents
