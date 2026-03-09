from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.mode_aggregate_support import decision_from_eligible_axes, scan_axes


@dataclass(frozen=True)
class AxisSafetyFacts:
    axis_id: str
    in_scope: bool
    estop_bits: dict[str, bool] | None = None
    axis_taster: bool | None = None
    axis_armed: bool | None = None
    axis_ready: bool | None = None
    axis_age_ms: int | None = None
    axis_owner: str | None = None


@dataclass(frozen=True)
class AggregateInputs:
    axes: Iterable[AxisSafetyFacts]
    stale_after_ms: int
    joy_deadman: bool = False
    joy_select_hip: bool = False
    joy_soll_speed: float = 0.0


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
    motion_allowed: bool = False


def _finish_result(
    *,
    core_mode: CoreMode,
    blocked_by: list[BlockedReason],
    axis_gate: dict[str, dict[str, object]],
    motion_allowed: bool = False,
) -> AggregateResult:
    if bool(motion_allowed) and core_mode != CoreMode.LIVE:
        raise AssertionError(
            "aggregate_core_mode contract violated: motion_allowed=True is only valid when core_mode==LIVE "
            f"(got core_mode={core_mode})"
        )
    if core_mode != CoreMode.LIVE:
        motion_allowed = False

    if core_mode == CoreMode.LIVE:
        allowed_live_codes = {"NO_SELECT_FOR_MOTION"}
        bad = [r for r in blocked_by if getattr(r, "code", None) not in allowed_live_codes]
        if bad:
            raise AssertionError(
                "aggregate_core_mode contract violated: LIVE must not carry hard blocked_by reasons "
                f"(bad={[getattr(r, 'code', None) for r in bad]})"
            )

    return AggregateResult(
        core_mode=core_mode,
        blocked_by=blocked_by,
        axis_gate=axis_gate,
        motion_allowed=bool(motion_allowed),
    )


def aggregate_core_mode(inputs: AggregateInputs) -> AggregateResult:
    axis_scan = scan_axes(
        axes=list(inputs.axes or []),
        stale_after_ms=int(inputs.stale_after_ms),
        make_blocked_reason=BlockedReason,
    )
    if axis_scan.has_missing_or_stale and axis_scan.eligible_axes:
        return _finish_result(
            core_mode=CoreMode.FAULT,
            blocked_by=list(axis_scan.blocked_by),
            axis_gate=axis_scan.axis_gate,
        )

    decision = decision_from_eligible_axes(
        eligible_axes=axis_scan.eligible_axes,
        axis_gate=axis_scan.axis_gate,
        blocked_by=list(axis_scan.blocked_by),
        joy_deadman=bool(inputs.joy_deadman),
        joy_select_hip=bool(inputs.joy_select_hip),
        joy_soll_speed=float(inputs.joy_soll_speed),
        make_blocked_reason=BlockedReason,
    )
    return _finish_result(
        core_mode=decision.core_mode,
        blocked_by=list(decision.blocked_by),
        axis_gate=axis_scan.axis_gate,
        motion_allowed=decision.motion_allowed,
    )
