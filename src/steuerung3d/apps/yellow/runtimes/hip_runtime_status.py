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


def resolve_hip_axis_selection(*, runtime: object, snap: object | None = None) -> HipAxisSelectionSnapshot:
    del snap
    engine = getattr(runtime, "engine", None)
    engine_state = getattr(engine, "state", None)
    selected_axis = str(getattr(engine_state, "selected_axis", "") or "")
    fixed_axis = str(getattr(runtime, "_fixed_axis", "") or "")
    axis_sel = resolve_runtime_axis(selected_axis=selected_axis, fixed_axis=fixed_axis)
    return HipAxisSelectionSnapshot(axis=str(axis_sel.axis or ""), attached=bool(axis_sel.attached))


def build_hip_motion_debug_snapshot(*, runtime: object, snap: object) -> HipMotionDebugSnapshot:
    axes = getattr(snap, "axes", {}) or {}
    axis_ids = sorted(list(axes.keys()))
    axis_sel = resolve_hip_axis_selection(runtime=runtime, snap=snap)
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
    axis_sel = resolve_hip_axis_selection(runtime=runtime)
    axis = axis_sel.axis
    estate = str(getattr(runtime, "_last_estate", "") or "")
    mode = str(getattr(runtime, "_last_mode", "") or "")
    armed = bool(str(estate or "").upper() in ("ARMED", "READY"))
    ready = bool(str(estate or "").upper() == "READY")
    age_disp = str(getattr(h, "age_disp", "") or "")
    engine = getattr(runtime, "engine", None)
    engine_state = getattr(engine, "state", None)
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


def build_hip_birdseye_payload(
    *,
    runtime: object,
    snap: object,
    intents: list[object],
    estate: str,
    soft_errors: dict[str, int] | None = None,
) -> HipBirdseyePayload:
    axis_sel = resolve_hip_axis_selection(runtime=runtime, snap=snap)
    axis = axis_sel.axis
    joy = getattr(getattr(runtime, "engine", None), "state", None)
    joy = getattr(joy, "joy", None) or getattr(snap, "joy", JoyState())

    try:
        raw_sp = float(getattr(joy, "soll_speed", 0.0) or 0.0)
    except Exception:
        raw_sp = 0.0
    joy_facts = extract_joy_facts(joy)
    sel = joy_selected_for_axis(joy=joy, axis_id=axis)
    joy_soll_speed_norm = joy_speed_for_axis(joy=joy, axis_id=axis)

    velmax = 0.0
    try:
        params = getattr(snap, "params", {}) or {}
        velmax = float(params.get("VelMax", 0.0) or 0.0)
    except Exception:
        velmax = 0.0
    if velmax < 0.0:
        velmax = 0.0

    joy_rate_mps = joy_soll_speed_norm * velmax if velmax > 0.0 else 0.0
    estop = bool(getattr(snap, "estop", False))
    fault = bool(getattr(snap, "fault", False))
    core_mode = str(getattr(snap, "core_mode", "") or "")
    armed = bool(str(estate or "").upper() in ("ARMED", "READY"))
    ready = bool(str(estate or "").upper() == "READY")

    enable: bool | None = None
    try:
        if axis:
            ax = getattr(snap, "axes", {}).get(axis)
            if ax is not None:
                enable = bool(ax.enable_cmd) if hasattr(ax, "enable_cmd") else bool(
                    getattr(ax, "enabled", False)
                )
    except Exception:
        enable = None

    types = sorted({type(i).__name__ for i in (intents or [])})
    intents_out_types = ",".join(types)
    intents_out_count = int(len(intents or []))

    summary = (
        f"hip axis={axis or '-'} core_mode={core_mode or '-'} "
        f"legacy_mode={estate or '-'} dm={int(bool(joy_facts.deadman))} sel={int(bool(sel))} "
        f"estop={int(estop)} v={joy_rate_mps:+.2f}m/s out=[{intents_out_types}]"
    )

    fields: dict[str, Any] = {
        "component": "hip",
        "axis_selected": str(axis or ""),
        "deadman": bool(joy_facts.deadman),
        "select_hip": bool(sel),
        "joy_soll_speed_norm": float(joy_soll_speed_norm),
        "raw_soll_speed": float(raw_sp),
        "velmax": float(velmax),
        "joy_rate_mps": float(joy_rate_mps),
        "intents_out_types": str(intents_out_types),
        "intents_out_count": int(intents_out_count),
        "estop": bool(estop),
        "fault": bool(fault),
        "mode": str(core_mode),
        "estate": str(estate or ""),
        "armed": bool(armed),
        "ready": bool(ready),
        "sel": bool(sel),
        "dm": bool(joy_facts.deadman),
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
