from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JoyFacts:
    """Normalized joystick facts used across core + UI.

    Semantics:
    - deadman: operator is holding the deadman switch.
    - select_hip: deprecated compatibility mirror; true iff any selected_axes exist.
    - soll_speed: commanded speed scalar (unitless policy input).
    """

    deadman: bool = False
    select_hip: bool = False
    soll_speed: float = 0.0


def extract_joy_facts(joy: object | None) -> JoyFacts:
    """Extract JoyFacts from a joy-like object.

    Accepts:
    - None
    - objects with attributes: deadman, selected_axes, soll_speed
    - legacy attr alias: select_hip / select only as compatibility fallback when selected_axes is absent
    """
    if joy is None:
        return JoyFacts()

    deadman = bool(getattr(joy, "deadman", False))
    raw_selected_axes = getattr(joy, "selected_axes", None)
    if raw_selected_axes is not None:
        try:
            select_hip = any(str(x).strip() for x in raw_selected_axes)
        except TypeError:
            select_hip = False
    elif hasattr(joy, "select_hip"):
        select_hip = bool(getattr(joy, "select_hip", False))
    else:
        select_hip = bool(getattr(joy, "select", False))

    try:
        soll_speed = float(getattr(joy, "soll_speed", 0.0) or 0.0)
    except Exception:
        soll_speed = 0.0

    return JoyFacts(deadman=deadman, select_hip=select_hip, soll_speed=soll_speed)
