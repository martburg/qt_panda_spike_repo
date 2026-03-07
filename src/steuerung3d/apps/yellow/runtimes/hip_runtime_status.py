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


def build_hip_motion_debug_snapshot(*, runtime: object, snap: object) -> HipMotionDebugSnapshot:
    axes = getattr(snap, "axes", {}) or {}
    axis_ids = sorted(list(axes.keys()))
    engine = getattr(runtime, "engine", None)
    engine_state = getattr(engine, "state", None)
    selected_axis = str(getattr(engine_state, "selected_axis", "") or "")
    fixed_axis = str(getattr(runtime, "_fixed_axis", "") or "")
    axis_sel = resolve_runtime_axis(selected_axis=selected_axis, fixed_axis=fixed_axis)
    motion_axis = axis_sel.axis
    if not motion_axis and len(axis_ids) == 1:
        motion_axis = axis_ids[0]

    owner = get_claim_owner(snap, motion_axis) if motion_axis else ""
    core_mode = str(getattr(snap, "core_mode", ""))
    legacy_mode = str(getattr(snap, "mode", ""))
    joy = getattr(snap, "joy", JoyState())
    joy_facts = extract_joy_facts(joy)
    joy_select_hip = joy_selected_for_axis(joy=joy, axis_id=motion_axis)
    joy_soll_speed = joy_speed_for_axis(joy=joy, axis_id=motion_axis)

    motion_enabled = (
        bool(motion_axis)
        and core_mode.upper() == "LIVE"
        and owner == str(getattr(runtime, "_hip_id", "") or "")
        and bool(joy_facts.deadman)
        and bool(joy_select_hip)
    )
    return HipMotionDebugSnapshot(
        core_mode=core_mode,
        legacy_mode=legacy_mode,
        motion_axis=motion_axis,
        owner=owner,
        motion_enabled=motion_enabled,
        joy_deadman=bool(joy_facts.deadman),
        joy_select_hip=bool(joy_select_hip),
        joy_soll_speed=float(joy_soll_speed),
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
    engine = getattr(runtime, "engine", None)
    engine_state = getattr(engine, "state", None)
    selected_axis = str(getattr(engine_state, "selected_axis", "") or "")
    fixed_axis = str(getattr(runtime, "_fixed_axis", "") or "")
    axis_sel = resolve_runtime_axis(selected_axis=selected_axis, fixed_axis=fixed_axis)
    axis = axis_sel.axis
    estate = str(getattr(runtime, "_last_estate", "") or "")
    mode = str(getattr(runtime, "_last_mode", "") or "")
    armed = bool(str(estate or "").upper() in ("ARMED", "READY"))
    ready = bool(str(estate or "").upper() == "READY")
    age_disp = str(getattr(h, "age_disp", "") or "")
    joy = getattr(engine_state, "joy", JoyState())
    joy_facts = extract_joy_facts(joy)
    joy_select_hip = joy_selected_for_axis(joy=joy, axis_id=axis)
    joy_soll_speed = joy_speed_for_axis(joy=joy, axis_id=axis)
    dm = 1 if joy_facts.deadman else 0
    sel = 1 if joy_select_hip else 0
    summary = (
        f"axis={axis or '-'} core_mode={mode or '-'} legacy_mode={estate or '-'} "
        f"age_ms={age_disp} JOY dm={dm} sel={sel} sp={joy_soll_speed:+.2f}"
    )
    fields = with_health_fields(
        {
            "axis": axis,
            "attached": bool(axis_sel.attached),
            "mode": mode,
            "estate": str(estate or ""),
            "armed": bool(armed),
            "ready": bool(ready),
            "joy_deadman": bool(joy_facts.deadman),
            "joy_select_hip": bool(joy_select_hip),
            "joy_soll_speed": float(joy_soll_speed),
            "debug": {
                "axis_selected": axis,
                "attached": bool(axis_sel.attached),
                "core_mode": mode,
                "legacy_mode": str(estate or ""),
                "joy_deadman": bool(joy_facts.deadman),
                "joy_select_hip": bool(joy_select_hip),
                "joy_soll_speed": float(joy_soll_speed),
                "last_rx_ns": getattr(runtime, "_last_rx_ns", None),
            },
        },
        health=h,
        estop=bool(getattr(runtime, "_last_estop", False)),
        fault=bool(getattr(runtime, "_last_fault", False)),
    )
    return HipStatusPayload(
        level=str(getattr(h, "level", "") or ""),
        summary=summary,
        fields=fields,
    )
