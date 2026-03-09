from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from steuerung3d.core.axis_selection import (
    joy_selected_for_axis,
    joy_speed_for_axis,
    resolve_runtime_axis,
)
from steuerung3d.core.joy_facts import extract_joy_facts
from steuerung3d.core.joy_state import JoyState

from ..engines.hip.intent_policy import get_claim_owner
from .runtime_kernel import compute_health, with_health_fields


@dataclass(frozen=True)
class HipStatusPayload:
    level: str
    summary: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class HipMotionDebugSnapshot:
    core_mode: str
    legacy_mode: str
    motion_axis: str
    owner: str
    motion_enabled: bool
    joy_deadman: bool
    joy_select_hip: bool
    joy_soll_speed: float


@dataclass(frozen=True)
class HipBirdseyePayload:
    summary: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class HipAxisSelectionSnapshot:
    axis: str
    attached: bool


@dataclass(frozen=True)
class HipRuntimeStatusFacts:
    axis: str
    attached: bool
    core_mode: str
    legacy_mode: str
    owner: str
    joy_deadman: bool
    joy_select_hip: bool
    joy_soll_speed: float
    raw_soll_speed: float


def resolve_hip_axis_selection(
    *, runtime: object, snap: object | None = None
) -> HipAxisSelectionSnapshot:
    del snap
    engine = getattr(runtime, "engine", None)
    engine_state = getattr(engine, "state", None)
    selected_axis = str(getattr(engine_state, "selected_axis", "") or "")
    fixed_axis = str(getattr(runtime, "_fixed_axis", "") or "")
    axis_sel = resolve_runtime_axis(selected_axis=selected_axis, fixed_axis=fixed_axis)
    return HipAxisSelectionSnapshot(axis=str(axis_sel.axis or ""), attached=bool(axis_sel.attached))


def build_runtime_status_facts(
    *, runtime: object, snap: object | None = None
) -> HipRuntimeStatusFacts:
    axis_sel = resolve_hip_axis_selection(runtime=runtime, snap=snap)
    axis = axis_sel.axis
    if snap is not None:
        axis_ids = sorted(list((getattr(snap, "axes", {}) or {}).keys()))
        if not axis and len(axis_ids) == 1:
            axis = axis_ids[0]

    core_mode = str(getattr(snap, "core_mode", getattr(runtime, "_last_mode", "")) or "")
    legacy_mode = str(getattr(snap, "mode", getattr(runtime, "_last_estate", "")) or "")

    engine = getattr(runtime, "engine", None)
    engine_state = getattr(engine, "state", None)
    joy = getattr(engine_state, "joy", None)
    if joy is None:
        joy = getattr(snap, "joy", JoyState()) if snap is not None else JoyState()
    try:
        raw_soll_speed = float(getattr(joy, "soll_speed", 0.0) or 0.0)
    except Exception:
        raw_soll_speed = 0.0
    joy_facts = extract_joy_facts(joy)
    joy_select_hip = joy_selected_for_axis(joy=joy, axis_id=axis)
    joy_soll_speed = joy_speed_for_axis(joy=joy, axis_id=axis)

    owner = get_claim_owner(snap, axis) if (snap is not None and axis) else ""
    return HipRuntimeStatusFacts(
        axis=str(axis or ""),
        attached=bool(axis_sel.attached),
        core_mode=core_mode,
        legacy_mode=legacy_mode,
        owner=str(owner or ""),
        joy_deadman=bool(joy_facts.deadman),
        joy_select_hip=bool(joy_select_hip),
        joy_soll_speed=float(joy_soll_speed),
        raw_soll_speed=float(raw_soll_speed),
    )


def build_hip_motion_debug_snapshot(*, runtime: object, snap: object) -> HipMotionDebugSnapshot:
    facts = build_runtime_status_facts(runtime=runtime, snap=snap)
    motion_enabled = (
        bool(facts.axis)
        and facts.core_mode.upper() == "LIVE"
        and facts.owner == str(getattr(runtime, "_hip_id", "") or "")
        and facts.joy_deadman
        and facts.joy_select_hip
    )
    return HipMotionDebugSnapshot(
        core_mode=facts.core_mode,
        legacy_mode=facts.legacy_mode,
        motion_axis=facts.axis,
        owner=facts.owner,
        motion_enabled=motion_enabled,
        joy_deadman=facts.joy_deadman,
        joy_select_hip=facts.joy_select_hip,
        joy_soll_speed=facts.joy_soll_speed,
    )


def build_hip_status_payload(*, runtime: object, now_ns: int) -> HipStatusPayload:
    h = compute_health(
        now_ns=int(now_ns),
        last_rx_ns=getattr(runtime, "_last_rx_ns", None),
        stale_after_ms=int(getattr(runtime, "_stale_after_ms", 0)),
        seen_first_rx=bool(getattr(runtime, "_seen_first_telem", False)),
        estop=bool(getattr(runtime, "_last_estop", False)),
        fault=bool(getattr(runtime, "_last_fault", False)),
    )
    facts = build_runtime_status_facts(runtime=runtime)
    estate = str(getattr(runtime, "_last_estate", "") or "")
    armed = bool(str(estate or "").upper() in ("ARMED", "READY"))
    ready = bool(str(estate or "").upper() == "READY")
    age_disp = str(getattr(h, "age_disp", "") or "")
    dm = 1 if facts.joy_deadman else 0
    sel = 1 if facts.joy_select_hip else 0
    summary = (
        f"axis={facts.axis or '-'} core_mode={facts.core_mode or '-'} legacy_mode={estate or '-'} "
        f"age_ms={age_disp} JOY dm={dm} sel={sel} sp={facts.joy_soll_speed:+.2f}"
    )
    fields = with_health_fields(
        {
            "axis": facts.axis,
            "attached": bool(facts.attached),
            "mode": facts.core_mode,
            "estate": str(estate or ""),
            "armed": bool(armed),
            "ready": bool(ready),
            "joy_deadman": bool(facts.joy_deadman),
            "joy_select_hip": bool(facts.joy_select_hip),
            "joy_soll_speed": float(facts.joy_soll_speed),
            "debug": {
                "axis_selected": facts.axis,
                "attached": bool(facts.attached),
                "core_mode": facts.core_mode,
                "legacy_mode": str(estate or ""),
                "joy_deadman": bool(facts.joy_deadman),
                "joy_select_hip": bool(facts.joy_select_hip),
                "joy_soll_speed": float(facts.joy_soll_speed),
                "last_rx_ns": getattr(runtime, "_last_rx_ns", None),
            },
        },
        health=h,
        estop=bool(getattr(runtime, "_last_estop", False)),
        fault=bool(getattr(runtime, "_last_fault", False)),
    )
    return HipStatusPayload(
        level=str(getattr(h, "level", "") or ""), summary=summary, fields=fields
    )


def build_hip_birdseye_payload(
    *,
    runtime: object,
    snap: object,
    intents: list[object],
    estate: str,
    soft_errors: dict[str, int] | None = None,
) -> HipBirdseyePayload:
    facts = build_runtime_status_facts(runtime=runtime, snap=snap)
    velmax = 0.0
    try:
        params = getattr(snap, "params", {}) or {}
        velmax = float(params.get("VelMax", 0.0) or 0.0)
    except Exception:
        velmax = 0.0
    if velmax < 0.0:
        velmax = 0.0

    joy_rate_mps = facts.joy_soll_speed * velmax if velmax > 0.0 else 0.0
    estop = bool(getattr(snap, "estop", False))
    fault = bool(getattr(snap, "fault", False))
    armed = bool(str(estate or "").upper() in ("ARMED", "READY"))
    ready = bool(str(estate or "").upper() == "READY")

    enable: bool | None = None
    try:
        if facts.axis:
            ax = getattr(snap, "axes", {}).get(facts.axis)
            if ax is not None:
                enable = (
                    bool(ax.enable_cmd)
                    if hasattr(ax, "enable_cmd")
                    else bool(getattr(ax, "enabled", False))
                )
    except Exception:
        enable = None

    types = sorted({type(i).__name__ for i in (intents or [])})
    intents_out_types = ",".join(types)
    intents_out_count = int(len(intents or []))

    summary = (
        f"hip axis={facts.axis or '-'} core_mode={facts.core_mode or '-'} "
        f"legacy_mode={estate or '-'} dm={int(bool(facts.joy_deadman))} sel={int(bool(facts.joy_select_hip))} "
        f"estop={int(estop)} v={joy_rate_mps:+.2f}m/s out=[{intents_out_types}]"
    )

    fields: dict[str, Any] = {
        "component": "hip",
        "axis_selected": str(facts.axis or ""),
        "deadman": bool(facts.joy_deadman),
        "select_hip": bool(facts.joy_select_hip),
        "joy_soll_speed_norm": float(facts.joy_soll_speed),
        "raw_soll_speed": float(facts.raw_soll_speed),
        "velmax": float(velmax),
        "joy_rate_mps": float(joy_rate_mps),
        "intents_out_types": str(intents_out_types),
        "intents_out_count": int(intents_out_count),
        "estop": bool(estop),
        "fault": bool(fault),
        "mode": str(facts.core_mode),
        "estate": str(estate or ""),
        "armed": bool(armed),
        "ready": bool(ready),
        "sel": bool(facts.joy_select_hip),
        "dm": bool(facts.joy_deadman),
    }
    if soft_errors:
        try:
            fields["soft_errors_total"] = int(sum(int(v) for v in soft_errors.values()))
            fields["soft_errors_by_key"] = {str(k): int(v) for k, v in soft_errors.items()}
        except Exception:
            pass
    if enable is not None:
        fields["enable"] = bool(enable)
    return HipBirdseyePayload(summary=summary, fields=fields)
