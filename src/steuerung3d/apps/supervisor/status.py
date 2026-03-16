from __future__ import annotations

from collections.abc import Iterable

from steuerung3d.core.telemetry import JoyState

from .models import AxisPhase, AxisRow


def build_status_text(*, rows: Iterable[AxisRow], joy: JoyState, hip_open_total: int) -> str:
    rows_t = tuple(rows)
    phases = {row.phase for row in rows_t}
    if not rows_t:
        state = "NO AXES"
    elif AxisPhase.ESTOP in phases:
        state = "ESTOP"
    elif AxisPhase.STALE in phases:
        state = "DEGRADED"
    elif AxisPhase.LIVE in phases:
        state = "LIVE"
    elif rows_t and all(row.phase == AxisPhase.READY for row in rows_t):
        state = "READY"
    elif AxisPhase.ARMED in phases:
        state = "ARMING"
    else:
        state = "IDLE"
    joy_state = "active" if bool(joy.deadman) and hip_open_total <= 0 else "online"
    status = f"System: {state} | axes: {len(rows_t)} | joystick: {joy_state}"
    if hip_open_total > 0:
        status += f" | hip: {hip_open_total} open | supervisor: locked"
    return status
