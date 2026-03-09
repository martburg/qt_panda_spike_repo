from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from steuerung3d.core.core_mode import CoreMode
from steuerung3d.protocol.estop_bits import ESTOP_CAUSE_KEYS, ESTOP_OK_KEYS

KEY0 = "Key0"
KEY1 = "Key1"
KEY2 = "Key2"

TWINSAFE_KEYS = {
    "g1_fb",
    "g1_com",
    "g1_out",
    "g2_fb",
    "g2_com",
    "g2_out",
    "g3_fb",
    "g3_com",
    "g3_out",
}

DYNAMIC_EXCLUDE = {
    "ready",
    "taster",
    "schuetz",
    "reset_able",
    "steuerwort",
    "key1_ok",
    "key2_ok",
    "schluessel1",
    "schluessel2",
}

KEY1_IGNORES = {"network", *TWINSAFE_KEYS}
KEY2_IGNORES = {"network", "guider", "dcs_ok", *TWINSAFE_KEYS}


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


@dataclass(frozen=True)
class _AxisGateFacts:
    axis: AxisSafetyFacts
    missing: list[str]
    stale: bool
    key_mode: str | None
    hard_estop_active: bool | None
    fault_estop_active: bool | None

    def as_gate_dict(self) -> dict[str, object]:
        return {
            "in_scope": bool(self.axis.in_scope),
            "key_mode": self.key_mode,
            "missing": bool(self.missing),
            "stale": bool(self.stale),
            "hard_estop_active": self.hard_estop_active,
            "fault_estop_active": self.fault_estop_active,
            "taster": self.axis.axis_taster,
            "armed": self.axis.axis_armed,
            "ready": self.axis.axis_ready,
            "owner": self.axis.axis_owner,
            "age_ms": self.axis.axis_age_ms,
        }


@dataclass(frozen=True)
class _EligibleAxisState:
    in_scope: list[AxisSafetyFacts]
    eligible: list[AxisSafetyFacts]
    blocked_by: list[BlockedReason]
    axis_gate: dict[str, dict[str, object]]
    has_missing_or_stale: bool


def _missing_fields(axis: AxisSafetyFacts) -> list[str]:
    missing: list[str] = []
    if axis.estop_bits is None:
        missing.append("estop_bits")
    if axis.axis_armed is None:
        missing.append("axis_armed")
    if axis.axis_ready is None:
        missing.append("axis_ready")
    if axis.axis_age_ms is None:
        missing.append("axis_age_ms")
    return missing


def _key_mode(bits: dict[str, bool] | None) -> str | None:
    if bits is None:
        return None
    if bool(bits.get("schluessel2", False)):
        return KEY2
    if bool(bits.get("schluessel1", False)):
        return KEY1
    return KEY0


def _key_ignored_keys(key_mode: str | None) -> set[str]:
    if key_mode == KEY2:
        return set(KEY2_IGNORES)
    if key_mode == KEY1:
        return set(KEY1_IGNORES)
    return set()


def _effective_estops(
    bits: dict[str, bool] | None,
    *,
    key_mode: str | None,
) -> tuple[bool | None, bool | None]:
    if bits is None:
        return None, None

    ignored = _key_ignored_keys(key_mode)
    hard_keys = {k for k in ESTOP_CAUSE_KEYS if k not in ignored}
    hard_active = any(bool(bits.get(k, False)) for k in hard_keys)

    ok_keys = {k for k in ESTOP_OK_KEYS if (k not in DYNAMIC_EXCLUDE) and (k not in ignored)}
    ok_fault = any(not bool(bits.get(k, True)) for k in ok_keys)

    other_fault_keys = {
        k
        for k in bits.keys()
        if k not in ESTOP_CAUSE_KEYS
        and k not in ESTOP_OK_KEYS
        and k not in DYNAMIC_EXCLUDE
        and k not in ignored
    }
    other_fault = any(bool(bits.get(k, False)) for k in other_fault_keys)

    return hard_active, (ok_fault or other_fault)


def _build_axis_gate_facts(axis: AxisSafetyFacts, *, stale_after_ms: int) -> _AxisGateFacts:
    missing = _missing_fields(axis) if axis.in_scope else []
    stale = False
    if axis.in_scope and not missing:
        try:
            stale = int(axis.axis_age_ms or 0) >= stale_after_ms
        except Exception:
            stale = True
    key_mode = _key_mode(axis.estop_bits)
    hard_estop_active, fault_estop_active = _effective_estops(axis.estop_bits, key_mode=key_mode)
    return _AxisGateFacts(
        axis=axis,
        missing=missing,
        stale=stale,
        key_mode=key_mode,
        hard_estop_active=hard_estop_active,
        fault_estop_active=fault_estop_active,
    )


def _build_eligible_axis_state(inputs: AggregateInputs) -> _EligibleAxisState:
    axes = list(inputs.axes or [])
    in_scope = [axis for axis in axes if bool(axis.in_scope)]
    blocked_by: list[BlockedReason] = []
    axis_gate: dict[str, dict[str, object]] = {}
    has_missing_or_stale = False
    stale_after_ms = int(inputs.stale_after_ms)

    for axis in axes:
        gate_facts = _build_axis_gate_facts(axis, stale_after_ms=stale_after_ms)
        axis_gate[axis.axis_id] = gate_facts.as_gate_dict()
        if not axis.in_scope:
            continue

        eligible = (gate_facts.key_mode == KEY0) or (gate_facts.key_mode is None)
        if gate_facts.missing and eligible:
            blocked_by.append(BlockedReason("MISSING", axis.axis_id, ",".join(gate_facts.missing)))
            has_missing_or_stale = True
            continue
        if gate_facts.stale and eligible:
            blocked_by.append(BlockedReason("STALE", axis.axis_id, None))
            has_missing_or_stale = True

    eligible_axes = [
        axis for axis in in_scope if axis_gate.get(axis.axis_id, {}).get("key_mode") == KEY0
    ]
    return _EligibleAxisState(
        in_scope=in_scope,
        eligible=eligible_axes,
        blocked_by=blocked_by,
        axis_gate=axis_gate,
        has_missing_or_stale=has_missing_or_stale,
    )


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


def _finish_with_axes(
    eligible_state: _EligibleAxisState,
    *,
    core_mode: CoreMode,
    blocked_by: list[BlockedReason] | None = None,
    motion_allowed: bool = False,
) -> AggregateResult:
    return _finish_result(
        core_mode=core_mode,
        blocked_by=list(eligible_state.blocked_by if blocked_by is None else blocked_by),
        axis_gate=eligible_state.axis_gate,
        motion_allowed=motion_allowed,
    )


def _append_blocked_reasons(
    blocked_by: list[BlockedReason],
    code: str,
    axes: list[AxisSafetyFacts],
) -> list[BlockedReason]:
    if not axes:
        return blocked_by
    blocked_by.extend(BlockedReason(code, axis.axis_id, None) for axis in axes)
    return blocked_by


def aggregate_core_mode(inputs: AggregateInputs) -> AggregateResult:
    eligible_state = _build_eligible_axis_state(inputs)

    if not eligible_state.eligible:
        blocked_by = list(eligible_state.blocked_by)
        blocked_by.append(BlockedReason("NO_KEY0_AXES", None, None))
        return _finish_with_axes(eligible_state, core_mode=CoreMode.FAULT, blocked_by=blocked_by)

    if eligible_state.has_missing_or_stale:
        return _finish_with_axes(eligible_state, core_mode=CoreMode.FAULT)

    estop_axes = [
        axis
        for axis in eligible_state.eligible
        if bool(eligible_state.axis_gate.get(axis.axis_id, {}).get("hard_estop_active", False))
    ]
    if estop_axes:
        blocked_by = _append_blocked_reasons(list(eligible_state.blocked_by), "ESTOP", estop_axes)
        return _finish_with_axes(eligible_state, core_mode=CoreMode.ESTOP, blocked_by=blocked_by)

    fault_axes = [
        axis
        for axis in eligible_state.eligible
        if bool(eligible_state.axis_gate.get(axis.axis_id, {}).get("fault_estop_active", False))
    ]
    if fault_axes:
        blocked_by = _append_blocked_reasons(list(eligible_state.blocked_by), "FAULT", fault_axes)
        return _finish_with_axes(eligible_state, core_mode=CoreMode.FAULT, blocked_by=blocked_by)

    not_armed = [axis for axis in eligible_state.eligible if not bool(axis.axis_armed)]
    if not_armed:
        blocked_by = _append_blocked_reasons(
            list(eligible_state.blocked_by), "NOT_ARMED", not_armed
        )
        return _finish_with_axes(
            eligible_state,
            core_mode=CoreMode.IDLE,
            blocked_by=blocked_by,
            motion_allowed=False,
        )

    not_ready = [axis for axis in eligible_state.eligible if not bool(axis.axis_ready)]
    if not_ready:
        blocked_by = _append_blocked_reasons(
            list(eligible_state.blocked_by), "NOT_READY", not_ready
        )
        return _finish_with_axes(
            eligible_state,
            core_mode=CoreMode.ARMED,
            blocked_by=blocked_by,
            motion_allowed=False,
        )

    if not inputs.joy_deadman:
        return _finish_with_axes(
            eligible_state,
            core_mode=CoreMode.READY,
            motion_allowed=False,
        )

    blocked_by = list(eligible_state.blocked_by)
    motion_allowed = True
    if (abs(float(inputs.joy_soll_speed)) > 1e-6) and (not inputs.joy_select_hip):
        blocked_by.append(BlockedReason("NO_SELECT_FOR_MOTION", None, None))
        motion_allowed = False
    return _finish_with_axes(
        eligible_state,
        core_mode=CoreMode.LIVE,
        blocked_by=blocked_by,
        motion_allowed=motion_allowed,
    )
