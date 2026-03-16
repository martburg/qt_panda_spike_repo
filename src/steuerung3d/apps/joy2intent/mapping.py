"""Joystick -> intent mapping (gamepad).

This module is intentionally small and test-driven.

Semantics (as validated by tests):
- Deadman must be held to enable motion.
- One or more "select" buttons choose which winches receive jog commands.
- When deadman is released, any previously enabled winches are disabled.
- Jog command is JogWinch(winch_id, rate) where rate is scaled by max_winch_mps,
  and additionally scaled by fine_scale when the fine button is held.

Note: The tests construct JoyRig(winches=[...]). Earlier iterations used
JoyRig(winch_ids=[...]); we accept both for backward compatibility.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from steuerung3d.core.control_context import ControlContext

# Compatibility re-exports for older tests/imports.
from .mapping_helpers import (
    _JoyBindingsLike,
    build_active_enable_intents,
    build_joy_state_update,
    build_motion_intents,
    build_release_intents,
    clear_active_selection_state,
    collect_input_facts,
    compute_manual_rate,
    previous_activity,
    update_state_active_selection,
)


@dataclass(frozen=True)
class JoyBindings:
    axes: dict[str, int]
    buttons: dict[str, int | Sequence[int]]
    deadzone: float
    expo: float
    select_buttons: list[int | Sequence[int]] = field(default_factory=list)
    invert: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class JoyLimits:
    """Operational limits for joy2intent mapping.

    These limits should come from `configs/services/joy2intent.toml`.
    """

    max_winch_mps: float
    fine_scale: float

    def max_speed(self) -> float:
        return float(self.max_winch_mps)


@dataclass(frozen=True)
class JoyRig:
    """Rig mapping for joy2intent.

    Tests use: JoyRig(winches=[...])
    Legacy/older code may use: JoyRig(winch_ids=[...])

    If both are provided, `winches` wins.
    """

    winches: list[str] = field(default_factory=list)
    winch_ids: list[str] = field(default_factory=list)

    def ordered_winch_ids(self) -> list[str]:
        return self.winches if self.winches else self.winch_ids


class JoyStateLike(Protocol):
    prev_deadman: bool
    prev_active_winch_idxs: set[int]


class JoyReportLike(Protocol):
    @property
    def axes(self) -> Sequence[float]: ...

    @property
    def buttons(self) -> Sequence[int]: ...


def synthesize_intents(
    st: JoyStateLike,
    rc: JoyReportLike,
    bind: _JoyBindingsLike,
    rig: JoyRig,
    lim: JoyLimits,
    hip_id: str = "hip",
    control_context: ControlContext | None = None,
    publish_local_manual: bool = True,
) -> list[object]:
    """Convert a joystick report into a list of core intents."""
    intents: list[object] = []
    rig_ids = rig.ordered_winch_ids()
    facts = collect_input_facts(rc=rc, bind=bind, rig_ids=rig_ids, control_context=control_context)

    publish_selected_axes = not (facts.use_contextual_local_manual and not publish_local_manual)
    intents.append(build_joy_state_update(facts, publish_selected_axes=publish_selected_axes))

    if not facts.deadman:
        prev = previous_activity(st=st, rig_ids=rig_ids)
        if prev.prev_deadman and prev.active_ids:
            intents.extend(
                build_release_intents(
                    active_ids=prev.active_ids,
                    hip_id=hip_id,
                    use_contextual_local_manual=(
                        facts.use_contextual_local_manual and publish_local_manual
                    ),
                )
            )
        clear_active_selection_state(st)
        return intents

    if facts.use_contextual_local_manual and not publish_local_manual:
        update_state_active_selection(
            st=st,
            selected_set=facts.selected_set,
            rig_ids=rig_ids,
            deadman=True,
        )
        return intents

    if facts.use_contextual_local_manual and not facts.motion_enabled:
        update_state_active_selection(
            st=st,
            selected_set=facts.selected_set,
            rig_ids=rig_ids,
            deadman=True,
        )
        return intents

    prev = previous_activity(st=st, rig_ids=rig_ids)
    current_active = prev.active_ids
    if not facts.use_contextual_local_manual:
        intents.extend(
            build_active_enable_intents(
                selected_set=facts.selected_set,
                current_active=current_active,
                hip_id=hip_id,
            )
        )

    rate = compute_manual_rate(axes=facts.axes, bind=bind, lim=lim, fine=facts.fine)
    intents.extend(
        build_motion_intents(
            selected_set=facts.selected_set,
            hip_id=hip_id,
            use_contextual_local_manual=(
                facts.use_contextual_local_manual and publish_local_manual
            ),
            deadman=facts.deadman,
            rate=rate,
        )
    )
    update_state_active_selection(
        st=st,
        selected_set=facts.selected_set,
        rig_ids=rig_ids,
        deadman=True,
    )
    return intents
