from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING

from steuerung3d.core.intents import EnableAxis, Intent, JogWinch

from ...domain.joy_motion_map import map_soll_speed_to_jog_winch
from .intent_policy import should_emit_enable, should_emit_speed

if TYPE_CHECKING:
    from .step_phase_motion import HipJoyProjectionState

log = logging.getLogger("hi_p")


def apply_axis_change_behavior(
    *,
    intents: list[Intent],
    state: object,
    hip_id: str,
    prev_jog_active: bool,
    prev_jog_axis: str,
    motion_axis_id: str,
) -> None:
    if prev_jog_active and prev_jog_axis and prev_jog_axis != str(motion_axis_id or ""):
        if should_emit_speed(getattr(state, "last_sent_speed_by_axis", {}), prev_jog_axis, 0.0):
            intents.append(JogWinch(winch_id=prev_jog_axis, rate=0.0, hip_id=hip_id))


def build_jog_active_intents(
    *,
    intents: list[Intent],
    state: object,
    hip_id: str,
    motion_axis_id: str,
    speed: float,
    params: Mapping[str, object],
) -> float:
    try:
        vel_max_mps = float(params.get("VelMax", 0.0) or 0.0)
    except Exception:
        vel_max_mps = 0.0
    if vel_max_mps <= 0.0 and abs(float(speed)) > 0.0:
        log.debug("HiP vel_max unavailable for axis %s", motion_axis_id)

    if should_emit_enable(getattr(state, "last_sent_enable_by_axis", {}), motion_axis_id, True):
        intents.append(EnableAxis(axis_id=motion_axis_id, enable=True, hip_id=hip_id))

    intent = map_soll_speed_to_jog_winch(
        winch_id=motion_axis_id,
        soll_speed=float(speed),
        vel_max=float(vel_max_mps),
        hip_id=hip_id,
    )
    if intent is None:
        return 0.0
    jog_rate = float(intent.rate)
    if should_emit_speed(
        getattr(state, "last_sent_speed_by_axis", {}),
        motion_axis_id,
        float(intent.rate),
    ):
        intents.append(intent)
    return jog_rate


def build_stop_intents(
    *,
    intents: list[Intent],
    state: object,
    hip_id: str,
    prev_jog_active: bool,
    prev_jog_axis: str,
    motion_axis_id: str,
    display_axis_id: str,
    joy: "HipJoyProjectionState",
) -> None:
    stop_axis_id = prev_jog_axis or str(motion_axis_id or display_axis_id or "")
    raw_speed_active = abs(joy.raw_soll_speed) > 1e-3
    stop_pulse_needed = bool(
        stop_axis_id
        and (
            prev_jog_active
            or raw_speed_active
            or (not joy.joy_deadman)
            or joy.raw_select_hip
            or joy.joy_select_hip
        )
    )
    if stop_axis_id and stop_pulse_needed:
        if should_emit_speed(getattr(state, "last_sent_speed_by_axis", {}), stop_axis_id, 0.0):
            intents.append(JogWinch(winch_id=stop_axis_id, rate=0.0, hip_id=hip_id))
        if (not joy.joy_deadman) and should_emit_enable(
            getattr(state, "last_sent_enable_by_axis", {}), stop_axis_id, False
        ):
            intents.append(EnableAxis(axis_id=stop_axis_id, enable=False, hip_id=hip_id))


def emit_motion_transition_logs(
    *,
    prev_jog_active: bool,
    prev_jog_axis: str,
    jog_allowed: bool,
    motion_axis_id: str,
    stop_reason: str,
    jog_rate: float,
) -> None:
    if prev_jog_active and (not jog_allowed or prev_jog_axis != str(motion_axis_id or "")):
        axis_for_log = prev_jog_axis or str(motion_axis_id or "")
        if axis_for_log:
            reason = stop_reason if not jog_allowed else "axis_changed"
            log.info("JOY jog stopped axis=%s reason=%s", axis_for_log, reason)
    if jog_allowed and (not prev_jog_active or prev_jog_axis != str(motion_axis_id or "")):
        if motion_axis_id:
            log.info("JOY jog enabled axis=%s vel=%.3f", motion_axis_id, jog_rate)
