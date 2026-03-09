from __future__ import annotations

from dataclasses import dataclass
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
class _AxisScan:
    axis_gate: dict[str, dict[str, object]]
    blocked_by: list[object]
    eligible_axes: list[object]
    has_missing_or_stale: bool


@dataclass(frozen=True)
class _AggregateDecision:
    core_mode: CoreMode
    blocked_by: list[object]
    motion_allowed: bool = False


def missing_fields(axis: object) -> list[str]:
    missing: list[str] = []
    if getattr(axis, "estop_bits", None) is None:
        missing.append("estop_bits")
    if getattr(axis, "axis_armed", None) is None:
        missing.append("axis_armed")
    if getattr(axis, "axis_ready", None) is None:
        missing.append("axis_ready")
    if getattr(axis, "axis_age_ms", None) is None:
        missing.append("axis_age_ms")
    return missing


def key_mode(bits: dict[str, bool] | None) -> str | None:
    if bits is None:
        return None
    if bool(bits.get("schluessel2", False)):
        return KEY2
    if bool(bits.get("schluessel1", False)):
        return KEY1
    return KEY0


def key_ignored_keys(key_mode: str | None) -> set[str]:
    if key_mode == KEY2:
        return set(KEY2_IGNORES)
    if key_mode == KEY1:
        return set(KEY1_IGNORES)
    return set()


def effective_estops(
    bits: dict[str, bool] | None, *, key_mode: str | None
) -> tuple[bool | None, bool | None]:
    if bits is None:
        return None, None

    ignored = key_ignored_keys(key_mode)
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


def scan_axes(
    *, axes: Iterable[object], stale_after_ms: int, make_blocked_reason: object
) -> _AxisScan:
    blocked_by: list[object] = []
    axis_gate: dict[str, dict[str, object]] = {}
    has_missing_or_stale = False
    in_scope: list[object] = []
    for axis in axes:
        if bool(getattr(axis, "in_scope", False)):
            in_scope.append(axis)
        missing = missing_fields(axis) if bool(getattr(axis, "in_scope", False)) else []
        stale = False
        if bool(getattr(axis, "in_scope", False)) and not missing:
            try:
                stale = int(getattr(axis, "axis_age_ms", 0) or 0) >= int(stale_after_ms)
            except Exception:
                stale = True
        km = key_mode(getattr(axis, "estop_bits", None))
        hard_estop_active, fault_estop_active = effective_estops(
            getattr(axis, "estop_bits", None),
            key_mode=km,
        )
        axis_id = str(getattr(axis, "axis_id", ""))
        axis_gate[axis_id] = {
            "in_scope": bool(getattr(axis, "in_scope", False)),
            "key_mode": km,
            "missing": bool(missing),
            "stale": bool(stale),
            "hard_estop_active": hard_estop_active,
            "fault_estop_active": fault_estop_active,
            "taster": getattr(axis, "axis_taster", None),
            "armed": getattr(axis, "axis_armed", None),
            "ready": getattr(axis, "axis_ready", None),
            "owner": getattr(axis, "axis_owner", None),
            "age_ms": getattr(axis, "axis_age_ms", None),
        }
        if not bool(getattr(axis, "in_scope", False)):
            continue
        eligible = (km == KEY0) or (km is None)
        if missing and eligible:
            blocked_by.append(make_blocked_reason("MISSING", axis_id, ",".join(missing)))
            has_missing_or_stale = True
            continue
        if stale and eligible:
            blocked_by.append(make_blocked_reason("STALE", axis_id, None))
            has_missing_or_stale = True

    eligible_axes = [
        axis
        for axis in in_scope
        if axis_gate.get(str(getattr(axis, "axis_id", "")), {}).get("key_mode") == KEY0
    ]
    return _AxisScan(
        axis_gate=axis_gate,
        blocked_by=blocked_by,
        eligible_axes=eligible_axes,
        has_missing_or_stale=has_missing_or_stale,
    )


def decision_from_eligible_axes(
    *,
    eligible_axes: list[object],
    axis_gate: dict[str, dict[str, object]],
    blocked_by: list[object],
    joy_deadman: bool,
    joy_select_hip: bool,
    joy_soll_speed: float,
    make_blocked_reason: object,
) -> _AggregateDecision:
    if not eligible_axes:
        blocked_by.append(make_blocked_reason("NO_KEY0_AXES", None, None))
        return _AggregateDecision(core_mode=CoreMode.FAULT, blocked_by=blocked_by)

    estop_axes = [
        axis
        for axis in eligible_axes
        if bool(
            axis_gate.get(str(getattr(axis, "axis_id", "")), {}).get("hard_estop_active", False)
        )
    ]
    if estop_axes:
        blocked_by.extend(
            [
                make_blocked_reason("ESTOP", str(getattr(axis, "axis_id", "")), None)
                for axis in estop_axes
            ]
        )
        return _AggregateDecision(core_mode=CoreMode.ESTOP, blocked_by=blocked_by)

    fault_axes = [
        axis
        for axis in eligible_axes
        if bool(
            axis_gate.get(str(getattr(axis, "axis_id", "")), {}).get("fault_estop_active", False)
        )
    ]
    if fault_axes:
        blocked_by.extend(
            [
                make_blocked_reason("FAULT", str(getattr(axis, "axis_id", "")), None)
                for axis in fault_axes
            ]
        )
        return _AggregateDecision(core_mode=CoreMode.FAULT, blocked_by=blocked_by)

    not_armed = [axis for axis in eligible_axes if not bool(getattr(axis, "axis_armed", False))]
    if not_armed:
        blocked_by.extend(
            [
                make_blocked_reason("NOT_ARMED", str(getattr(axis, "axis_id", "")), None)
                for axis in not_armed
            ]
        )
        return _AggregateDecision(core_mode=CoreMode.IDLE, blocked_by=blocked_by)

    not_ready = [axis for axis in eligible_axes if not bool(getattr(axis, "axis_ready", False))]
    if not_ready:
        blocked_by.extend(
            [
                make_blocked_reason("NOT_READY", str(getattr(axis, "axis_id", "")), None)
                for axis in not_ready
            ]
        )
        return _AggregateDecision(core_mode=CoreMode.ARMED, blocked_by=blocked_by)

    if not bool(joy_deadman):
        return _AggregateDecision(core_mode=CoreMode.READY, blocked_by=blocked_by)

    motion_allowed = True
    if (abs(float(joy_soll_speed)) > 1e-6) and (not bool(joy_select_hip)):
        blocked_by.append(make_blocked_reason("NO_SELECT_FOR_MOTION", None, None))
        motion_allowed = False
    return _AggregateDecision(
        core_mode=CoreMode.LIVE, blocked_by=blocked_by, motion_allowed=motion_allowed
    )
