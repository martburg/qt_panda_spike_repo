from __future__ import annotations

from collections.abc import Sequence

from steuerung3d.core.intents import (
    ClaimAxis,
    EnableAxis,
    JogWinch,
    LocalAxisManualRequest,
)

from .axis_math import apply_deadzone_and_expo
from .mapping_types import _JoyBindingsLike, _JoyLimitsLike


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
