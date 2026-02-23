from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from steuerung3d.core.core_mode import CoreMode


@dataclass(frozen=True)
class AxisSafetyFacts:
    axis_id: str
    in_scope: bool
    axis_estop: bool | None = None
    axis_started: bool | None = None
    axis_fault: bool | None = None
    axis_taster_enabled: bool | None = None
    axis_armed: bool | None = None
    axis_ready: bool | None = None
    axis_age_ms: int | None = None
    axis_owner: str | None = None


@dataclass(frozen=True)
class AggregateInputs:
    axes: Iterable[AxisSafetyFacts]
    stale_after_ms: int
    joy_deadman: bool = False
    joy_select: bool = False
    live_request: bool = False


@dataclass(frozen=True)
class BlockedReason:
    code: str
    axis_id: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class AggregateResult:
    core_mode: CoreMode
    blocked_by: list[BlockedReason] = field(default_factory=list)
    axis_gate: dict[str, dict[str, object]] = field(default_factory=dict)


def _missing_fields(axis: AxisSafetyFacts) -> list[str]:
    missing: list[str] = []
    if axis.axis_estop is None:
        missing.append("axis_estop")
    if axis.axis_started is None:
        missing.append("axis_started")
    if axis.axis_fault is None:
        missing.append("axis_fault")
    if axis.axis_taster_enabled is None:
        missing.append("axis_taster_enabled")
    if axis.axis_armed is None:
        missing.append("axis_armed")
    if axis.axis_ready is None:
        missing.append("axis_ready")
    if axis.axis_age_ms is None:
        missing.append("axis_age_ms")
    return missing


def aggregate_core_mode(inputs: AggregateInputs) -> AggregateResult:
    axes = list(inputs.axes or [])
    in_scope = [axis for axis in axes if bool(axis.in_scope)]

    blocked_by: list[BlockedReason] = []
    axis_gate: dict[str, dict[str, object]] = {}
    stale_after_ms = int(inputs.stale_after_ms)

    has_missing_or_stale = False
    for axis in axes:
        missing = _missing_fields(axis) if axis.in_scope else []
        stale = False
        if axis.in_scope and not missing:
            try:
                stale = int(axis.axis_age_ms or 0) >= stale_after_ms
            except Exception:
                stale = True

        axis_gate[axis.axis_id] = {
            "in_scope": bool(axis.in_scope),
            "missing": bool(missing),
            "stale": bool(stale),
            "estop": axis.axis_estop,
            "fault": axis.axis_fault,
            "started": axis.axis_started,
            "taster_enabled": axis.axis_taster_enabled,
            "armed": axis.axis_armed,
            "ready": axis.axis_ready,
            "owner": axis.axis_owner,
            "age_ms": axis.axis_age_ms,
        }

        if not axis.in_scope:
            continue

        if missing:
            blocked_by.append(BlockedReason("MISSING", axis.axis_id, ",".join(missing)))
            has_missing_or_stale = True
            continue
        if stale:
            blocked_by.append(BlockedReason("STALE", axis.axis_id, None))
            has_missing_or_stale = True

    if not in_scope:
        blocked_by.append(BlockedReason("MISSING", None, "no_in_scope_axes"))
        return AggregateResult(core_mode=CoreMode.ESTOP, blocked_by=blocked_by, axis_gate=axis_gate)

    if has_missing_or_stale:
        return AggregateResult(core_mode=CoreMode.ESTOP, blocked_by=blocked_by, axis_gate=axis_gate)

    estop_axes = [axis for axis in in_scope if bool(axis.axis_estop)]
    if estop_axes:
        blocked_by.extend([BlockedReason("ESTOP", axis.axis_id, None) for axis in estop_axes])
        return AggregateResult(core_mode=CoreMode.ESTOP, blocked_by=blocked_by, axis_gate=axis_gate)

    fault_axes = [axis for axis in in_scope if bool(axis.axis_fault)]
    if fault_axes:
        blocked_by.extend([BlockedReason("FAULT", axis.axis_id, None) for axis in fault_axes])
        return AggregateResult(core_mode=CoreMode.ESTOP, blocked_by=blocked_by, axis_gate=axis_gate)

    not_started = [axis for axis in in_scope if not bool(axis.axis_started)]
    if not_started:
        blocked_by.extend([BlockedReason("NOT_STARTED", axis.axis_id, None) for axis in not_started])
        return AggregateResult(core_mode=CoreMode.IDLE, blocked_by=blocked_by, axis_gate=axis_gate)

    not_ready: list[AxisSafetyFacts] = []
    for axis in in_scope:
        if bool(axis.axis_taster_enabled):
            ready = bool(axis.axis_ready)
        else:
            ready = True
        if not ready:
            not_ready.append(axis)

    if not_ready:
        blocked_by.extend([BlockedReason("NOT_READY", axis.axis_id, None) for axis in not_ready])
        return AggregateResult(core_mode=CoreMode.ARMED, blocked_by=blocked_by, axis_gate=axis_gate)

    if inputs.live_request and inputs.joy_deadman and inputs.joy_select:
        return AggregateResult(core_mode=CoreMode.LIVE, blocked_by=blocked_by, axis_gate=axis_gate)

    if not inputs.live_request:
        blocked_by.append(BlockedReason("NO_LIVE_REQUEST", None, None))
    else:
        if not inputs.joy_deadman:
            blocked_by.append(BlockedReason("NO_DEADMAN", None, None))
        if not inputs.joy_select:
            blocked_by.append(BlockedReason("NO_SELECT", None, None))

    return AggregateResult(core_mode=CoreMode.READY, blocked_by=blocked_by, axis_gate=axis_gate)


def aggregate_and_store(state, inputs: AggregateInputs) -> AggregateResult:
    result = aggregate_core_mode(inputs)
    state.core_mode = result.core_mode
    state.core_blocked_by = list(result.blocked_by)
    state.core_axis_gate = dict(result.axis_gate)
    return result
