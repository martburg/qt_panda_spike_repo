from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List

from steuerung3d.core.core_mode import core_mode_value
from steuerung3d.core.joy_facts import extract_joy_facts
from steuerung3d.core.motion_gate import axis_local_motion_allowed

from .reporter_axis_detail import build_blocked_and_axes_snapshot


@dataclass(frozen=True)
class _BirdsEyeAgeFacts:
    age_int: float | None
    age_dev: float | None
    age_cmd: float | None
    age_ui: float | None
    age_c2: float | None
    stale: bool


@dataclass(frozen=True)
class _BirdsEyeMotionFacts:
    axes_snapshot: list[dict[str, object]]
    blocked_by: list[str]
    blocked_payload: list[dict[str, object]]
    cmd_frame: Any
    selected_lanes: list[str]
    attached_lanes: list[str]
    resolved_moving_targets: list[str]
    local_manual_axes: list[str]
    joy_dm: bool
    joy_sel: bool
    intents_types_str: str
    reset_denied_by_axis: dict[str, object]
    reset_denied_total: int
    devices: list[str]


def _compute_age_facts(*, last_seen: Dict[str, object]) -> _BirdsEyeAgeFacts:
    now = time.monotonic()
    age_int = None if last_seen["intent_ts"] is None else (now - float(last_seen["intent_ts"]))
    age_dev = (
        None if last_seen["dev_telem_ts"] is None else (now - float(last_seen["dev_telem_ts"]))
    )
    age_cmd = None if last_seen["cmd_ts"] is None else (now - float(last_seen["cmd_ts"]))
    age_ui = None if last_seen["ui_telem_ts"] is None else (now - float(last_seen["ui_telem_ts"]))
    age_c2 = None if last_seen["c2_telem_ts"] is None else (now - float(last_seen["c2_telem_ts"]))
    stale = any(age is not None and age > 2.0 for age in (age_int, age_dev))
    return _BirdsEyeAgeFacts(
        age_int=age_int,
        age_dev=age_dev,
        age_cmd=age_cmd,
        age_ui=age_ui,
        age_c2=age_c2,
        stale=stale,
    )


def _compute_level(*, snap: Any, age_facts: _BirdsEyeAgeFacts) -> tuple[str, bool, bool, str]:
    estop_v = bool(getattr(snap, "estop", False))
    fault_v = bool(getattr(snap, "fault", False))
    mode_v = core_mode_value(getattr(snap, "core_mode", "")) or str(getattr(snap, "core_mode", ""))
    level = "ERR" if (estop_v or fault_v) else ("WARN" if age_facts.stale else "OK")
    return level, estop_v, fault_v, mode_v


def _compute_reset_denied(*, state: Any) -> tuple[dict[str, object], int]:
    reset_denied_by_axis = dict(getattr(state, "estop_reset_denied_count_by_axis", {}) or {})
    try:
        reset_denied_total = sum(int(v) for v in reset_denied_by_axis.values())
    except Exception:
        reset_denied_total = 0
    return reset_denied_by_axis, reset_denied_total


def _build_motion_facts(
    *,
    snap: Any,
    state: Any,
    router: Any,
    axis_ids: List[str],
    last_intents_meta: Dict[str, object],
) -> _BirdsEyeMotionFacts:
    intents_types = last_intents_meta.get("types", []) or []
    intents_types_str = ",".join([str(t) for t in intents_types])
    reset_denied_by_axis, reset_denied_total = _compute_reset_denied(state=state)

    try:
        axes_snapshot, blocked_by, blocked_payload, cmd_frame = build_blocked_and_axes_snapshot(
            snap=snap,
            state=state,
            router=router,
            axis_ids=axis_ids,
        )
    except Exception:
        axes_snapshot = []
        blocked_by = []
        blocked_payload = []
        cmd_frame = None

    joy = getattr(state, "joy", None)
    jf = extract_joy_facts(joy)
    joy_dm = bool(jf.deadman)
    joy_sel = bool(jf.select_hip)
    selected_lanes = (
        sorted([str(x) for x in tuple(getattr(joy, "selected_axes", ()) or ()) if str(x).strip()])
        if joy is not None
        else []
    )
    attached_lanes = sorted(
        [
            f"{axis_id}:{owner}"
            for axis_id, owner in dict(getattr(state, "axis_claims", {}) or {}).items()
            if str(owner or "")
        ]
    )
    resolved_moving_targets = (
        sorted(
            [
                str(axis_id)
                for axis_id, sp in dict(getattr(cmd_frame, "axes", {}) or {}).items()
                if abs(float(getattr(sp, "vel", 0.0) or 0.0)) > 1e-9
            ]
        )
        if cmd_frame is not None
        else []
    )
    local_manual_axes = [
        axis_id
        for axis_id in selected_lanes
        if axis_id in axis_ids and axis_local_motion_allowed(state, axis_id)
    ]

    try:
        densis = getattr(snap, "densis", {}) or {}
        devices = sorted([str(k) for k in densis.keys()])
    except Exception:
        devices = []

    return _BirdsEyeMotionFacts(
        axes_snapshot=axes_snapshot,
        blocked_by=blocked_by[:3],
        blocked_payload=blocked_payload,
        cmd_frame=cmd_frame,
        selected_lanes=selected_lanes,
        attached_lanes=attached_lanes,
        resolved_moving_targets=resolved_moving_targets,
        local_manual_axes=local_manual_axes,
        joy_dm=joy_dm,
        joy_sel=joy_sel,
        intents_types_str=intents_types_str,
        reset_denied_by_axis=reset_denied_by_axis,
        reset_denied_total=reset_denied_total,
        devices=devices,
    )


def _build_summary(
    *,
    mode_v: str,
    state: Any,
    motion_facts: _BirdsEyeMotionFacts,
    last_intents_meta: Dict[str, object],
) -> str:
    blocked_summary = ",".join(motion_facts.blocked_by)
    motion_allowed_i = int(bool(getattr(state, "core_motion_allowed", False)))
    return (
        f"core_mode={mode_v} motion_allowed={motion_allowed_i} blocked_by=[{blocked_summary}] "
        f"local_manual=[{','.join(motion_facts.local_manual_axes)}] dm={int(motion_facts.joy_dm)} "
        f"sel=[{','.join(motion_facts.selected_lanes)}] moving=[{','.join(motion_facts.resolved_moving_targets)}] "
        f"in=[{motion_facts.intents_types_str}] n={int(last_intents_meta.get('count', 0))} "
        f"reset_denied={int(motion_facts.reset_denied_total)}"
    )


def _age_ms(age: float | None) -> float | None:
    return None if age is None else age * 1000.0


def _build_fields(
    *,
    snap: Any,
    state: Any,
    mode_v: str,
    estop_v: bool,
    fault_v: bool,
    age_facts: _BirdsEyeAgeFacts,
    motion_facts: _BirdsEyeMotionFacts,
    last_intents_meta: Dict[str, object],
) -> dict[str, object]:
    cmd_frame = motion_facts.cmd_frame
    return {
        "component": "core",
        "core_mode": str(mode_v),
        "blocked_by": list(motion_facts.blocked_payload),
        "joy_dm": bool(motion_facts.joy_dm),
        "joy_sel": bool(motion_facts.joy_sel),
        "deadman": bool(motion_facts.joy_dm),
        "selected_lanes": list(motion_facts.selected_lanes),
        "attached_lanes": list(motion_facts.attached_lanes),
        "resolved_moving_targets": list(motion_facts.resolved_moving_targets),
        "motion_allowed": bool(getattr(state, "core_motion_allowed", False)),
        "local_manual_axes": list(motion_facts.local_manual_axes),
        "local_manual_allowed": bool(motion_facts.local_manual_axes),
        "tick": int(getattr(snap, "tick", 0) or 0),
        "mode": str(mode_v),
        "estop": estop_v,
        "fault": fault_v,
        "intents_in_count": int(last_intents_meta.get("count", 0)),
        "intents_in_types": motion_facts.intents_types_str,
        "cmd_estop_reset": bool(getattr(cmd_frame, "estop_reset", False))
        if cmd_frame is not None
        else False,
        "cmd_resync": bool(getattr(cmd_frame, "resync", False)) if cmd_frame is not None else False,
        "axes": motion_facts.axes_snapshot,
        "reset_denied_total": int(motion_facts.reset_denied_total),
        "reset_denied_by_axis": dict(motion_facts.reset_denied_by_axis),
        "devices": motion_facts.devices[:32],
        "devices_n": len(motion_facts.devices),
        "age_int_ms": _age_ms(age_facts.age_int),
        "age_dev_ms": _age_ms(age_facts.age_dev),
        "age_cmd_ms": _age_ms(age_facts.age_cmd),
        "age_ui_ms": _age_ms(age_facts.age_ui),
        "age_c2_ms": _age_ms(age_facts.age_c2),
    }


def emit_birds_eye_status(
    *,
    status,
    snap,
    state,
    router,
    axis_ids: List[str],
    last_intents_meta: Dict[str, object],
    last_seen: Dict[str, object],
) -> None:
    if status is None:
        return

    try:
        age_facts = _compute_age_facts(last_seen=last_seen)
        level, estop_v, fault_v, mode_v = _compute_level(snap=snap, age_facts=age_facts)
        motion_facts = _build_motion_facts(
            snap=snap,
            state=state,
            router=router,
            axis_ids=axis_ids,
            last_intents_meta=last_intents_meta,
        )
        status.emit_every(
            level=level,
            summary=_build_summary(
                mode_v=mode_v,
                state=state,
                motion_facts=motion_facts,
                last_intents_meta=last_intents_meta,
            ),
            fields=_build_fields(
                snap=snap,
                state=state,
                mode_v=mode_v,
                estop_v=estop_v,
                fault_v=fault_v,
                age_facts=age_facts,
                motion_facts=motion_facts,
                last_intents_meta=last_intents_meta,
            ),
        )
    except Exception:
        return
