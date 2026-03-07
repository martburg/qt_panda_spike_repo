from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from steuerung3d.core.intents import EnableAxis, Intent, JogWinch

from ...domain.joy_motion_map import map_soll_speed_to_jog_winch
from .intent_policy import get_claim_owner, should_emit_enable, should_emit_speed
from .joy_projection import project_joy
from .motion_target import resolve_motion_axis_id

log = logging.getLogger("hi_p")


@dataclass(frozen=True)
class HipJoyProjectionState:
    joy_deadman: bool
    joy_select_hip: bool
    joy_soll_speed: float
    raw_select_hip: bool
    raw_soll_speed: float


@dataclass(frozen=True)
class HipMotionPhaseResult:
    intents: list[Intent]
    joy: HipJoyProjectionState
    jog_allowed: bool
    jog_rate: float
    motion_axis_id: str
    stop_reason: str


def project_local_joy(*, joy: object, display_axis_id: str) -> HipJoyProjectionState:
    joyp = project_joy(joy=joy, display_axis_id=str(display_axis_id or ""))
    return HipJoyProjectionState(
        joy_deadman=bool(joyp.deadman),
        joy_select_hip=bool(joyp.select_hip),
        joy_soll_speed=float(joyp.soll_speed),
        raw_select_hip=bool(joyp.raw_select_hip),
        raw_soll_speed=float(joyp.raw_soll_speed),
    )


def compute_motion_phase(
    *,
    state: object,
    snap: object,
    hip_id: str,
    axis_id: str,
    axis_ids: list[str],
    display_axis_id: str,
    mode_now: str,
    estop: bool,
    fault: bool,
    axes: dict[str, Any],
    joy: HipJoyProjectionState,
    logical: dict[str, Any],
    estate: str,
    params: dict[str, Any],
) -> HipMotionPhaseResult:
    motion_axis_id = resolve_motion_axis_id(
        axis_id=str(axis_id or ""),
        axis_ids=list(axis_ids),
        joy_deadman=bool(joy.joy_deadman),
        joy_select_hip=bool(joy.joy_select_hip),
        axes=axes,
    )

    prev_jog_active = bool(getattr(state, "joy_jog_active", False))
    prev_jog_axis = str(getattr(state, "joy_jog_axis", "") or "")

    axis_in_scope = bool(motion_axis_id and motion_axis_id in axes)
    axis = axes.get(motion_axis_id) if axis_in_scope else None
    axis_fault = bool(getattr(axis, "fault", False)) if axis is not None else False

    owner = get_claim_owner(snap, motion_axis_id) if motion_axis_id else ""
    owner_ok = owner == str(hip_id or "")

    speed = float(joy.joy_soll_speed)
    speed_active = abs(speed) > 1e-3
    armed_ok = str(estate or "").upper() in ("ARMED", "READY")
    ready_ok = bool(logical.get("ready", False))
    taster = bool(logical.get("taster", False))

    jog_allowed = (
        axis_in_scope
        and (str(mode_now).upper() == "LIVE")
        and (not estop)
        and (not fault)
        and (not axis_fault)
        and bool(taster)
        and bool(armed_ok)
        and bool(ready_ok)
        and owner_ok
        and joy.joy_deadman
        and joy.joy_select_hip
        and speed_active
    )

    def _jog_block_reason() -> str:
        if not motion_axis_id:
            return "no_axis"
        if not axis_in_scope:
            return "axis_missing"
        if str(mode_now).upper() != "LIVE":
            return f"mode={str(mode_now)}"
        if estop:
            return "estop"
        if fault or axis_fault:
            return "fault"
        if not taster:
            return "taster"
        if not armed_ok:
            return "armed"
        if not ready_ok:
            return "ready"
        if not owner_ok:
            return f"owner={owner or '-'}"
        if not joy.joy_deadman:
            return "deadman"
        if not joy.joy_select_hip:
            return "select"
        if not speed_active:
            return "zero_speed"
        return "unknown"

    intents: list[Intent] = []
    if prev_jog_active and prev_jog_axis and prev_jog_axis != str(motion_axis_id or ""):
        if should_emit_speed(
            getattr(state, "last_sent_speed_by_axis", {}),
            prev_jog_axis,
            0.0,
        ):
            intents.append(JogWinch(winch_id=prev_jog_axis, rate=0.0, hip_id=hip_id))

    jog_rate = 0.0
    stop_reason = ""
    if jog_allowed:
        try:
            vel_max_mps = float(params.get("VelMax", 0.0) or 0.0)
        except Exception:
            vel_max_mps = 0.0
        if vel_max_mps <= 0.0 and abs(float(speed)) > 0.0:
            log.debug("HiP vel_max unavailable for axis %s", motion_axis_id)

        if should_emit_enable(
            getattr(state, "last_sent_enable_by_axis", {}),
            motion_axis_id,
            True,
        ):
            intents.append(EnableAxis(axis_id=motion_axis_id, enable=True, hip_id=hip_id))

        intent = map_soll_speed_to_jog_winch(
            winch_id=motion_axis_id,
            soll_speed=float(speed),
            vel_max=float(vel_max_mps),
            hip_id=hip_id,
        )
        if intent is not None:
            jog_rate = float(intent.rate)
            if should_emit_speed(
                getattr(state, "last_sent_speed_by_axis", {}),
                motion_axis_id,
                float(intent.rate),
            ):
                intents.append(intent)
    else:
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
            if should_emit_speed(
                getattr(state, "last_sent_speed_by_axis", {}),
                stop_axis_id,
                0.0,
            ):
                intents.append(JogWinch(winch_id=stop_axis_id, rate=0.0, hip_id=hip_id))
            if (not joy.joy_deadman) and should_emit_enable(
                getattr(state, "last_sent_enable_by_axis", {}),
                stop_axis_id,
                False,
            ):
                intents.append(EnableAxis(axis_id=stop_axis_id, enable=False, hip_id=hip_id))
        stop_reason = _jog_block_reason()

    if prev_jog_active and (not jog_allowed or prev_jog_axis != str(motion_axis_id or "")):
        axis_for_log = prev_jog_axis or str(motion_axis_id or "")
        if axis_for_log:
            reason = stop_reason if not jog_allowed else "axis_changed"
            log.info("JOY jog stopped axis=%s reason=%s", axis_for_log, reason)

    if jog_allowed and (not prev_jog_active or prev_jog_axis != str(motion_axis_id or "")):
        if motion_axis_id:
            log.info("JOY jog enabled axis=%s vel=%.3f", motion_axis_id, jog_rate)

    return HipMotionPhaseResult(
        intents=intents,
        joy=joy,
        jog_allowed=bool(jog_allowed),
        jog_rate=float(jog_rate),
        motion_axis_id=str(motion_axis_id or ""),
        stop_reason=str(stop_reason or ""),
    )
