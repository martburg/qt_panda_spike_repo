"""Motion target resolution helpers for HiP.

No semantic changes intended; extracted from :mod:`step_impl`.
"""

from __future__ import annotations

from typing import Mapping


def resolve_motion_axis_id(
    *,
    axis_id: str,
    axis_ids: list[str],
    joy_deadman: bool,
    joy_select_hip: bool,
    axes: Mapping[str, object],
) -> str:
    """Resolve motion axis id.

    Normally, motion is directed to the currently attached axis (``axis_id``).
    For single-axis bring-up, we allow motion even when the UI isn't fully
    configured yet, but only when it would be unambiguous.
    """

    motion_axis_id = axis_id
    if not motion_axis_id and len(axis_ids) == 1 and joy_deadman and joy_select_hip:
        actionable: list[str] = []
        for axis_key in axis_ids:
            ax = axes.get(axis_key)
            if ax is None:
                continue

            in_scope = getattr(ax, "in_scope", True)
            if in_scope is None:
                in_scope = True
            if not bool(in_scope):
                continue

            if bool(getattr(ax, "fault", False)):
                continue

            actionable.append(str(axis_key))

        if len(actionable) == 1:
            # Single-axis bring-up: avoid ambiguous selection mapping.
            motion_axis_id = actionable[0]

    return str(motion_axis_id or "")
