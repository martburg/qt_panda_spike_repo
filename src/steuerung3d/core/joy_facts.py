from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class JoyFacts:
    """Normalized joystick facts used across core + UI.

    Semantics:
    - deadman: operator is holding the deadman switch.
    - select_hip: operator has explicitly selected/armed control (SEL gate).
    - soll_speed: commanded speed scalar (unitless policy input).
    """
    deadman: bool = False
    select_hip: bool = False
    soll_speed: float = 0.0


def extract_joy_facts(joy: object | None) -> JoyFacts:
    """Extract JoyFacts from a joy-like object.

    Accepts:
    - None
    - objects with attributes: deadman, select_hip, soll_speed
    - legacy attr alias: select (falls back to select_hip if present)
    """
    if joy is None:
        return JoyFacts()

    deadman = bool(getattr(joy, "deadman", False))
    # Prefer explicit select_hip; fall back to legacy 'select'
    if hasattr(joy, "select_hip"):
        select_hip = bool(getattr(joy, "select_hip", False))
    else:
        select_hip = bool(getattr(joy, "select", False))

    try:
        soll_speed = float(getattr(joy, "soll_speed", 0.0) or 0.0)
    except Exception:
        soll_speed = 0.0

    return JoyFacts(deadman=deadman, select_hip=select_hip, soll_speed=soll_speed)
