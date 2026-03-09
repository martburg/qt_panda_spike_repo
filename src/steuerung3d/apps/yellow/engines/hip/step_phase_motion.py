from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from steuerung3d.core.axis_selection import resolve_motion_axis_id
from steuerung3d.core.intents import EnableAxis, Intent, JogWinch

from ...domain.joy_motion_map import map_soll_speed_to_jog_winch
from .intent_policy import get_claim_owner, should_emit_enable, should_emit_speed
from .joy_projection import project_joy

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


@dataclass(frozen=True)
class _AxisContext:
    motion_axis_id: str
    axis_in_scope: bool
    axis_fault: bool
    owner: str
    owner_ok: bool


def _resolve_axis_context(
    *,
    snap: object,
    hip_id: str,
    axis_id: str,
    axis_ids: list[str],
    joy: HipJoyProjectionState,
    axes: dict[str, Any],
) -> _AxisContext:
    motion_axis_id = resolve_motion_axis_id(
        axis_id=str(axis_id or ""),
        axis_ids=list(axis_ids),
        joy_deadman=bool(joy.joy_deadman),
        joy_select_hip=bool(joy.joy_select_hip),
        axes=axes,
    )
    axis_in_scope = bool(motion_axis_id and motion_axis_id in axes)
    axis = axes.get(motion_axis_id) if axis_in_scope else None
    axis_fault = bool(getattr(axis, "fault", False)) if axis is not None else False
    owner = get_claim_owner(snap, motion_axis_id) if motion_axis_id else ""
    owner_ok = owner == str(hip_id or "")
    return _AxisContext(
        motion_axis_id=str(motion_axis_id or ""),
        axis_in_scope=bool(axis_in_scope),
        axis_fault=bool(axis_fault),
        owner=str(owner or ""),
        owner_ok=bool(owner_ok),
    )


def _compute_jog_allowed(
    *,
    axis_ctx: _AxisContext,
    mode_now: str,
    estop: bool,
    fault: bool,
    taster: bool,
    armed_ok: bool,
    ready_ok: bool,
    joy: HipJoyProjectionState,
    speed_active: bool,
) -> bool:
    return (
        axis_ctx.axis_in_scope
        and (str(mode_now).upper() == "LIVE")
        and (not estop)
        and (not fault)
        and (not axis_ctx.axis_fault)
        and bool(taster)
        and bool(armed_ok)
        and bool(ready_ok)
        and axis_ctx.owner_ok
        and joy.joy_deadman
        and joy.joy_select_hip
        and speed_active
    )


def _compute_jog_block_reason(
    *,
    axis_ctx: _AxisContext,
    mode_now: str,
    estop: bool,
    fault: bool,
    taster: bool,
    armed_ok: bool,
    ready_ok: bool,
    joy: HipJoyProjectionState,
    speed_active: bool,
) -> str:
    if not axis_ctx.motion_axis_id:
        return "no_axis"
    if not axis_ctx.axis_in_scope:
        return "axis_missing"
    if str(mode_now).upper() != "LIVE":
        return f"mode={str(mode_now)}"
    if estop:
        return "estop"
    if fault or axis_ctx.axis_fault:
        return "fault"
    if not taster:
        return "taster"
    if not armed_ok:
        return "armed"
    if not ready_ok:
        return "ready"
    if not axis_ctx.owner_ok:
        return f"owner={axis_ctx.owner or '-'}"
    if not joy.joy_deadman:
        return "deadman"
    if not joy.joy_select_hip:
        return "select"
    if not speed_active:
        return "zero_speed"
    return "unknown"


def _append_axis_change_stop_intent(
    *, intents: list[Intent], state: object, prev_jog_axis: str, motion_axis_id: str, hip_id: str
) -> None:
    if prev_jog_axis and prev_jog_axis != str(motion_axis_id or ""):
        if should_emit_speed(
            getattr(state, "last_sent_speed_by_axis", {}),
            prev_jog_axis,
            0.0,
        ):
            intents.append(JogWinch(winch_id=prev_jog_axis, rate=0.0, hip_id=hip_id))


def _build_jog_active_intents(
    *,
    intents: list[Intent],
    state: object,
    hip_id: str,
    motion_axis_id: str,
    speed: float,
    params: dict[str, Any],
) -> float:
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


def _build_stop_intents(
    *,
    intents: list[Intent],
    state: object,
    hip_id: str,
    prev_jog_active: bool,
    prev_jog_axis: str,
    motion_axis_id: str,
    display_axis_id: str,
    joy: HipJoyProjectionState,
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


def _emit_motion_transition_logs(
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
    axis_ctx = _resolve_axis_context(
        snap=snap,
        hip_id=hip_id,
        axis_id=axis_id,
        axis_ids=axis_ids,
        joy=joy,
        axes=axes,
    )

    prev_jog_active = bool(getattr(state, "joy_jog_active", False))
    prev_jog_axis = str(getattr(state, "joy_jog_axis", "") or "")

    speed = float(joy.joy_soll_speed)
    speed_active = abs(speed) > 1e-3
    armed_ok = str(estate or "").upper() in ("ARMED", "READY")
    ready_ok = bool(logical.get("ready", False))
    taster = bool(logical.get("taster", False))

    jog_allowed = _compute_jog_allowed(
        axis_ctx=axis_ctx,
        mode_now=mode_now,
        estop=estop,
        fault=fault,
        taster=taster,
        armed_ok=armed_ok,
        ready_ok=ready_ok,
        joy=joy,
        speed_active=speed_active,
    )

    intents: list[Intent] = []
    if prev_jog_active:
        _append_axis_change_stop_intent(
            intents=intents,
            state=state,
            prev_jog_axis=prev_jog_axis,
            motion_axis_id=axis_ctx.motion_axis_id,
            hip_id=hip_id,
        )

    jog_rate = 0.0
    stop_reason = ""
    if jog_allowed:
        jog_rate = _build_jog_active_intents(
            intents=intents,
            state=state,
            hip_id=hip_id,
            motion_axis_id=axis_ctx.motion_axis_id,
            speed=speed,
            params=params,
        )
    else:
        _build_stop_intents(
            intents=intents,
            state=state,
            hip_id=hip_id,
            prev_jog_active=prev_jog_active,
            prev_jog_axis=prev_jog_axis,
            motion_axis_id=axis_ctx.motion_axis_id,
            display_axis_id=display_axis_id,
            joy=joy,
        )
        stop_reason = _compute_jog_block_reason(
            axis_ctx=axis_ctx,
            mode_now=mode_now,
            estop=estop,
            fault=fault,
            taster=taster,
            armed_ok=armed_ok,
            ready_ok=ready_ok,
            joy=joy,
            speed_active=speed_active,
        )

    _emit_motion_transition_logs(
        prev_jog_active=prev_jog_active,
        prev_jog_axis=prev_jog_axis,
        jog_allowed=jog_allowed,
        motion_axis_id=axis_ctx.motion_axis_id,
        stop_reason=stop_reason,
        jog_rate=jog_rate,
    )

    return HipMotionPhaseResult(
        intents=intents,
        joy=joy,
        jog_allowed=bool(jog_allowed),
        jog_rate=float(jog_rate),
        motion_axis_id=str(axis_ctx.motion_axis_id or ""),
        stop_reason=str(stop_reason or ""),
    )
