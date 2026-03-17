from __future__ import annotations

from steuerung3d.core.telemetry import JoyState

from .models import AxisPhase


def is_live_motion(*, ax: object, joy: JoyState) -> bool:
    if ax is None:
        return False
    if not bool(joy.deadman):
        return False
    return abs(float(getattr(ax, "vel", 0.0) or 0.0)) > 1e-6 or abs(float(joy.soll_speed)) > 1e-6



def phase_from_facts(*, estate: str, stale: bool, live_motion: bool) -> AxisPhase:
    if stale:
        return AxisPhase.STALE
    if live_motion:
        return AxisPhase.LIVE
    estate_s = str(estate or "").upper()
    if estate_s == "READY":
        return AxisPhase.READY
    if estate_s == "ARMED":
        return AxisPhase.ARMED
    if estate_s == "IDLE":
        return AxisPhase.IDLE
    return AxisPhase.ESTOP
