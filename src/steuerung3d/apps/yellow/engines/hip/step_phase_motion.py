from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, cast

from steuerung3d.core.intents import Intent
from steuerung3d.core.joy_state import JoyState

from .joy_projection import project_joy
from .step_phase_motion_context import (
    AxisContext,
    MotionDecision,
    compute_motion_decision,
    resolve_axis_context,
)
from .step_phase_motion_emit import (
    apply_axis_change_behavior,
    build_jog_active_intents,
    build_stop_intents,
    emit_motion_transition_logs,
)


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
    joyp = project_joy(joy=cast(JoyState | None, joy), display_axis_id=str(display_axis_id or ""))
    return HipJoyProjectionState(
        joy_deadman=bool(joyp.deadman),
        joy_select_hip=bool(joyp.select_hip),
        joy_soll_speed=float(joyp.soll_speed),
        raw_select_hip=bool(joyp.raw_select_hip),
        raw_soll_speed=float(joyp.raw_soll_speed),
    )


def _build_motion_result(
    *,
    intents: list[Intent],
    joy: HipJoyProjectionState,
    decision: MotionDecision,
    jog_rate: float,
    motion_axis_id: str,
) -> HipMotionPhaseResult:
    return HipMotionPhaseResult(
        intents=intents,
        joy=joy,
        jog_allowed=bool(decision.jog_allowed),
        jog_rate=float(jog_rate),
        motion_axis_id=str(motion_axis_id or ""),
        stop_reason=str(decision.stop_reason or ""),
    )


def _run_motion_branch(
    *,
    intents: list[Intent],
    state: object,
    hip_id: str,
    prev_jog_active: bool,
    prev_jog_axis: str,
    axis_ctx: AxisContext,
    display_axis_id: str,
    joy: HipJoyProjectionState,
    decision: MotionDecision,
    params: Mapping[str, object],
) -> float:
    apply_axis_change_behavior(
        intents=intents,
        state=state,
        hip_id=hip_id,
        prev_jog_active=prev_jog_active,
        prev_jog_axis=prev_jog_axis,
        motion_axis_id=axis_ctx.motion_axis_id,
    )
    if decision.jog_allowed:
        return build_jog_active_intents(
            intents=intents,
            state=state,
            hip_id=hip_id,
            motion_axis_id=axis_ctx.motion_axis_id,
            speed=decision.speed,
            params=params,
        )
    build_stop_intents(
        intents=intents,
        state=state,
        hip_id=hip_id,
        prev_jog_active=prev_jog_active,
        prev_jog_axis=prev_jog_axis,
        motion_axis_id=axis_ctx.motion_axis_id,
        display_axis_id=display_axis_id,
        joy=joy,
    )
    return 0.0


def compute_motion_phase(
    *,
    state: object,
    snap: object,
    hip_id: str,
    axis_id: str,
    axis_ids: Sequence[str],
    display_axis_id: str,
    mode_now: str,
    estop: bool,
    fault: bool,
    axes: Mapping[str, object],
    joy: HipJoyProjectionState,
    logical: Mapping[str, object],
    estate: str,
    params: Mapping[str, object],
) -> HipMotionPhaseResult:
    axis_ctx = resolve_axis_context(
        snap=snap,
        hip_id=hip_id,
        axis_id=axis_id,
        axis_ids=axis_ids,
        joy=joy,
        axes=axes,
    )
    prev_jog_active = bool(getattr(state, "joy_jog_active", False))
    prev_jog_axis = str(getattr(state, "joy_jog_axis", "") or "")
    decision = compute_motion_decision(
        axis_ctx=axis_ctx,
        mode_now=mode_now,
        estop=estop,
        fault=fault,
        taster=bool(logical.get("taster", False)),
        armed_ok=str(estate or "").upper() in ("ARMED", "READY"),
        ready_ok=bool(logical.get("ready", False)),
        joy=joy,
    )
    intents: list[Intent] = []
    jog_rate = _run_motion_branch(
        intents=intents,
        state=state,
        hip_id=hip_id,
        prev_jog_active=prev_jog_active,
        prev_jog_axis=prev_jog_axis,
        axis_ctx=axis_ctx,
        display_axis_id=display_axis_id,
        joy=joy,
        decision=decision,
        params=params,
    )
    emit_motion_transition_logs(
        prev_jog_active=prev_jog_active,
        prev_jog_axis=prev_jog_axis,
        jog_allowed=decision.jog_allowed,
        motion_axis_id=axis_ctx.motion_axis_id,
        stop_reason=decision.stop_reason,
        jog_rate=jog_rate,
    )
    return _build_motion_result(
        intents=intents,
        joy=joy,
        decision=decision,
        jog_rate=jog_rate,
        motion_axis_id=axis_ctx.motion_axis_id,
    )
