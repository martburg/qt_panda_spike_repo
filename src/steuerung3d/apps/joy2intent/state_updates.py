from __future__ import annotations

from collections.abc import Sequence

from steuerung3d.core.intents import JoyStateUpdate

from .mapping_types import (
    JoyInputFacts,
    PreviousActivity,
    _IndexedJoyStateLike,
    _JoyStateLike,
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
    if isinstance(st, _IndexedJoyStateLike):
        prev_deadman = bool(st.prev_deadman)
        active_ids = {str(rig_ids[i]) for i in st.prev_active_winch_idxs if 0 <= i < len(rig_ids)}
        return PreviousActivity(prev_deadman=prev_deadman, active_ids=active_ids)

    prev_deadman = bool(st.deadman_prev)
    active_ids = {str(axis_id) for axis_id in st.enabled_winch_ids}
    return PreviousActivity(prev_deadman=prev_deadman, active_ids=active_ids)


def update_state_active_selection(
    *, st: _JoyStateLike, selected_set: set[str], rig_ids: Sequence[str], deadman: bool
) -> None:
    if isinstance(st, _IndexedJoyStateLike):
        st.prev_active_winch_idxs = {rig_ids.index(w) for w in selected_set if w in rig_ids}
        st.prev_deadman = bool(deadman)
        return

    st.enabled_winch_ids = set(selected_set)
    st.deadman_prev = bool(deadman)


def clear_active_selection_state(st: _JoyStateLike) -> None:
    if isinstance(st, _IndexedJoyStateLike):
        st.prev_active_winch_idxs.clear()
        st.prev_deadman = False
        return

    st.enabled_winch_ids.clear()
    st.deadman_prev = False
