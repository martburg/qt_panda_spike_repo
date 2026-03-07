"""Joystick projection helpers for HiP.

These helpers take the raw joystick report (as carried in telemetry snapshots)
and derive the *axis-local* view that the HiP uses:

- deadman is global
- selection + soll_speed are local to the currently displayed axis

No semantic changes intended; extracted from :mod:`step_impl`.
"""

from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.core.joy_state import JoyState


@dataclass(frozen=True, slots=True)
class JoyProjection:
    """Axis-local joy view."""

    deadman: bool
    select_hip: bool
    soll_speed: float
    raw_select_hip: bool
    raw_soll_speed: float


def project_joy(*, joy: JoyState | None, display_axis_id: str) -> JoyProjection:
    """Project raw joy state to an axis-local view.

    The raw joy report contains global deadman and a set of selected axes.
    The HiP uses this to decide whether the *current* axis is selected and
    to zero speed when it is not.
    """

    j = joy or JoyState()
    deadman = bool(getattr(j, "deadman", False))
    raw_select_hip = bool(getattr(j, "select_hip", False))
    raw_soll_speed = float(getattr(j, "soll_speed", 0.0) or 0.0)

    selected_axes = tuple(getattr(j, "selected_axes", ()) or ())
    selected_axis_set = {str(x).strip() for x in selected_axes if str(x).strip()}

    if selected_axis_set:
        local_selected = bool(display_axis_id) and display_axis_id in selected_axis_set
    else:
        local_selected = False

    select_hip = bool(local_selected)
    soll_speed = float(raw_soll_speed if local_selected else 0.0)

    return JoyProjection(
        deadman=deadman,
        select_hip=select_hip,
        soll_speed=soll_speed,
        raw_select_hip=raw_select_hip,
        raw_soll_speed=raw_soll_speed,
    )
