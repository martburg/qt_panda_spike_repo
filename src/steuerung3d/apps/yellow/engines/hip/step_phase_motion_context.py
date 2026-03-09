from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from steuerung3d.core.axis_selection import resolve_motion_axis_id

from .intent_policy import get_claim_owner

if TYPE_CHECKING:
    from .step_phase_motion import HipJoyProjectionState


@dataclass(frozen=True)
class AxisContext:
    motion_axis_id: str
    axis_in_scope: bool
    axis_fault: bool
    owner: str
    owner_ok: bool


@dataclass(frozen=True)
class MotionDecision:
    jog_allowed: bool
    stop_reason: str
    speed: float


def resolve_axis_context(
    *,
    snap: object,
    hip_id: str,
    axis_id: str,
    axis_ids: list[str],
    joy: "HipJoyProjectionState",
    axes: dict[str, Any],
) -> AxisContext:
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
    return AxisContext(
        motion_axis_id=str(motion_axis_id or ""),
        axis_in_scope=bool(axis_in_scope),
        axis_fault=bool(axis_fault),
        owner=str(owner or ""),
        owner_ok=bool(owner_ok),
    )


def compute_jog_allowed(
    *,
    axis_ctx: AxisContext,
    mode_now: str,
    estop: bool,
    fault: bool,
    taster: bool,
    armed_ok: bool,
    ready_ok: bool,
    joy: "HipJoyProjectionState",
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


def compute_jog_block_reason(
    *,
    axis_ctx: AxisContext,
    mode_now: str,
    estop: bool,
    fault: bool,
    taster: bool,
    armed_ok: bool,
    ready_ok: bool,
    joy: "HipJoyProjectionState",
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


def compute_motion_decision(
    *,
    axis_ctx: AxisContext,
    mode_now: str,
    estop: bool,
    fault: bool,
    taster: bool,
    armed_ok: bool,
    ready_ok: bool,
    joy: "HipJoyProjectionState",
) -> MotionDecision:
    speed = float(joy.joy_soll_speed)
    speed_active = abs(speed) > 1e-3
    jog_allowed = compute_jog_allowed(
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
    stop_reason = ""
    if not jog_allowed:
        stop_reason = compute_jog_block_reason(
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
    return MotionDecision(
        jog_allowed=bool(jog_allowed),
        stop_reason=str(stop_reason or ""),
        speed=float(speed),
    )
