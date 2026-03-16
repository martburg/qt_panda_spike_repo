from __future__ import annotations

from collections.abc import Sequence

from steuerung3d.core.intents import JoyStateUpdate

from .mapping_types import JoyInputFacts, PreviousActivity, _JoyStateLike


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
