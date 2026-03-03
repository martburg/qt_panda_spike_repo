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

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence, Set

from steuerung3d.core.intents import ClaimAxis, EnableAxis, JogWinch, JoyStateUpdate
from steuerung3d.core.joy_state import clamp_soll_speed


@dataclass(frozen=True)
class JoyBindings:
    # Mapping from logical axis name -> index in rc.axes
    axes: Dict[str, int]
    # Mapping from logical button name -> button index
    buttons: Dict[str, int]
    # Required (non-default) settings must appear before defaulted fields (dataclasses rule)
    deadzone: float
    expo: float
    # Button indices used to select winches by position (0..N-1)
    select_buttons: List[int] = field(default_factory=list)
    # Optional axis inversion by logical axis name
    invert: Dict[str, bool] = field(default_factory=dict)


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

    winches: List[str] = field(default_factory=list)
    winch_ids: List[str] = field(default_factory=list)

    def ordered_winch_ids(self) -> List[str]:
        return self.winches if self.winches else self.winch_ids


@dataclass
class JoyState:
    # Previously enabled winches while deadman was held
    enabled_winch_ids: Set[str] = field(default_factory=set)
    deadman_prev: bool = False


@dataclass(frozen=True)
class JoyReport:
    # Raw controller report used by tests
    axes: List[float]
    pressed: Set[int] = field(default_factory=set)

    @classmethod
    def from_parts(cls, axes: Sequence[float], pressed: Iterable[int] = ()) -> "JoyReport":
        return cls(list(axes), set(pressed))


def _apply_deadzone_and_expo(x: float, deadzone: float, expo: float) -> float:
    """Map x in [-1,1] through deadzone+expo curve."""
    if deadzone < 0:
        deadzone = 0.0
    if deadzone > 0.95:
        deadzone = 0.95

    ax = abs(x)
    if ax <= deadzone:
        return 0.0

    # Normalize remaining range to [0,1]
    y = (ax - deadzone) / (1.0 - deadzone)
    if expo <= 0:
        expo = 1.0
    y = y**expo
    return y if x >= 0 else -y


def _apply_deadzone_only(x: float, deadzone: float) -> float:
    if deadzone < 0:
        deadzone = 0.0
    if deadzone > 0.95:
        deadzone = 0.95
    if abs(x) <= deadzone:
        return 0.0
    return x


def _pressed_buttons(rc: Any) -> Set[int]:
    """Return set of pressed button indices for different rc types."""
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


def _axes(rc: Any) -> List[float]:
    if hasattr(rc, "axes"):
        try:
            return list(rc.axes)
        except Exception:
            return []
    return []


def synthesize_intents(
    st: JoyState,
    rc: JoyReport,
    bind: JoyBindings,
    rig: JoyRig,
    lim: JoyLimits,
    # Must match the claim owner (HiP) to avoid the core treating motion intents as stale.
    hip_id: str = "hip",
) -> List[object]:
    """Convert a joystick report into a list of core intents.

    This function is designed to satisfy tests in tests/test_joy2intent_gamepad.py.
    """
    intents: List[object] = []

    deadman_btn = bind.buttons.get("deadman")
    fine_btn = bind.buttons.get("fine")
    pressed = _pressed_buttons(rc)
    axes = _axes(rc)

    deadman = (deadman_btn is not None) and (deadman_btn in pressed)
    fine = (fine_btn is not None) and (fine_btn in pressed)

    select_btn = bind.buttons.get("select_hip")
    select_hip = (select_btn is not None) and (select_btn in pressed)

    soll_speed = 0.0
    soll_axis = bind.axes.get("soll_speed")
    if soll_axis is not None and 0 <= soll_axis < len(axes):
        soll_speed = float(axes[soll_axis])
        if bind.invert.get("soll_speed", False):
            soll_speed = -soll_speed
        soll_speed = _apply_deadzone_only(soll_speed, bind.deadzone)
    soll_speed = clamp_soll_speed(soll_speed)

    intents.append(
        JoyStateUpdate(
            deadman=bool(deadman),
            select_hip=bool(select_hip),
            soll_speed=float(soll_speed),
        )
    )

    rig_ids = rig.ordered_winch_ids()

    # Determine which winches are selected (by select_buttons index).
    selected: List[str] = []
    for i, b in enumerate(bind.select_buttons or []):
        if b in pressed and i < len(rig_ids):
            selected.append(rig_ids[i])

    # Legacy arbitration: even if multiple select buttons are held, only one
    # winch is targeted (lowest index wins). This mirrors the original
    # "one active hip" behavior and avoids accidental multi-winch jogging.
    if len(selected) > 1:
        selected = [selected[0]]

    selected_set = set(selected)

    if deadman and select_hip and (not selected_set) and len(rig_ids) == 1:
        # Single-winch fallback for ambiguous select button mappings during bring-up.
        selected_set = {rig_ids[0]}

    # Deadman released: disable any previously enabled winches.
    if not deadman:
        prev_deadman = bool(getattr(st, "prev_deadman", getattr(st, "deadman_prev", False)))
        prev_active = set(
            getattr(st, "prev_active_winch_idxs", getattr(st, "enabled_winch_ids", set()))
        )

        active_ids: Set[str] = set()
        if prev_active and all(isinstance(x, int) for x in prev_active):
            active_ids = {rig_ids[i] for i in prev_active if 0 <= i < len(rig_ids)}
        else:
            active_ids = {str(x) for x in prev_active}

        if prev_deadman and active_ids:
            for wid in sorted(active_ids):
                intents.append(EnableAxis(axis_id=wid, enable=False, hip_id=hip_id))
        if hasattr(st, "prev_active_winch_idxs"):
            st.prev_active_winch_idxs.clear()
        elif hasattr(st, "enabled_winch_ids"):
            st.enabled_winch_ids.clear()
        if hasattr(st, "prev_deadman"):
            st.prev_deadman = False
        else:
            st.deadman_prev = False
        return intents

    # Deadman pressed: enable selected winches and issue jogs.
    current_active_raw = set(
        getattr(st, "prev_active_winch_idxs", getattr(st, "enabled_winch_ids", set()))
    )
    if current_active_raw and all(isinstance(x, int) for x in current_active_raw):
        current_active = {rig_ids[i] for i in current_active_raw if 0 <= i < len(rig_ids)}
    else:
        current_active = {str(x) for x in current_active_raw}
    # Important:
    # - ClaimAxis is only needed on the transition (avoid spam).
    # - EnableAxis(True) is safe/idempotent, and we intentionally *repeat it*
    #   while deadman is held.
    #
    # Rationale: the core may temporarily be in FAULT/IDLE while deadman+select
    # are already pressed (e.g. fault/ESTOP clearing and legacy READY coming in).
    # If EnableAxis(True) is only emitted on the first transition, it can be
    # dropped by core safety gating and never re-sent, leaving cmd_en=0 even
    # though JogWinch continues to stream.
    for wid in sorted(selected_set):
        if wid not in current_active:
            intents.append(ClaimAxis(axis_id=wid, hip_id=hip_id))
        intents.append(EnableAxis(axis_id=wid, enable=True, hip_id=hip_id))

    # Compute jog rate
    axis_idx = bind.axes.get("manual_jog")
    raw = 0.0
    # axes already fetched above
    if axis_idx is not None and 0 <= axis_idx < len(axes):
        raw = float(axes[axis_idx])
    if bind.invert.get("manual_jog", False):
        raw = -raw

    shaped = _apply_deadzone_and_expo(raw, bind.deadzone, bind.expo)
    rate = shaped * lim.max_speed()
    if fine:
        rate *= float(lim.fine_scale)

    if rate != 0.0:
        for wid in sorted(selected_set):
            intents.append(JogWinch(winch_id=wid, rate=rate, hip_id=hip_id))
    if hasattr(st, "prev_active_winch_idxs"):
        # tests expect indices; derive from rig order
        st.prev_active_winch_idxs = {rig_ids.index(w) for w in selected_set if w in rig_ids}
    elif hasattr(st, "enabled_winch_ids"):
        st.enabled_winch_ids = set(selected_set)

    if hasattr(st, "prev_deadman"):
        st.prev_deadman = True
    else:
        st.deadman_prev = True
    return intents
