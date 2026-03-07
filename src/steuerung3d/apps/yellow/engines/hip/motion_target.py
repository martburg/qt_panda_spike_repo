"""Motion target resolution helpers for HiP.

No semantic changes intended; extracted from :mod:`step_impl`.
"""

from __future__ import annotations

from typing import Mapping

from steuerung3d.core.axis_selection import resolve_motion_axis_id as _resolve_motion_axis_id


def resolve_motion_axis_id(
    *,
    axis_id: str,
    axis_ids: list[str],
    joy_deadman: bool,
    joy_select_hip: bool,
    axes: Mapping[str, object],
) -> str:
    return _resolve_motion_axis_id(
        axis_id=axis_id,
        axis_ids=axis_ids,
        joy_deadman=joy_deadman,
        joy_select_hip=joy_select_hip,
        axes=axes,
    )
