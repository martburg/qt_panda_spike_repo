from __future__ import annotations

import time
from collections.abc import Sequence

from steuerung3d.core.core_mode import core_mode_value
from steuerung3d.core.joy_facts import extract_joy_facts

from .birds_eye_types import (
    BirdsEyeAgeFacts,
    BirdsEyeAxisDetailStateLike,
    BirdsEyeMotionFacts,
    BirdsEyeRouterLike,
    BirdsEyeSnapLike,
    LastIntentsMetaLike,
    LastSeenLike,
)
from .reporter_axis_detail import build_blocked_and_axes_snapshot


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _as_optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, (str, bytes, bytearray)):
        return []
    if not isinstance(value, Sequence):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return sorted(out)


def compute_age_facts(*, last_seen: LastSeenLike) -> BirdsEyeAgeFacts:
    now = time.monotonic()
    age_int_ts = _as_optional_float(last_seen.get("intent_ts"))
    age_dev_ts = _as_optional_float(last_seen.get("dev_telem_ts"))
    age_cmd_ts = _as_optional_float(last_seen.get("cmd_ts"))
    age_ui_ts = _as_optional_float(last_seen.get("ui_telem_ts"))
    age_c2_ts = _as_optional_float(last_seen.get("c2_telem_ts"))

    age_int = None if age_int_ts is None else (now - age_int_ts)
    age_dev = None if age_dev_ts is None else (now - age_dev_ts)
    age_cmd = None if age_cmd_ts is None else (now - age_cmd_ts)
    age_ui = None if age_ui_ts is None else (now - age_ui_ts)
    age_c2 = None if age_c2_ts is None else (now - age_c2_ts)
    stale = any(age is not None and age > 2.0 for age in (age_int, age_dev))
    return BirdsEyeAgeFacts(
        age_int=age_int,
        age_dev=age_dev,
        age_cmd=age_cmd,
        age_ui=age_ui,
        age_c2=age_c2,
        stale=stale,
    )


def compute_level(
    *, snap: BirdsEyeSnapLike, age_facts: BirdsEyeAgeFacts
) -> tuple[str, bool, bool, str]:
    estop_v = bool(snap.estop)
    fault_v = bool(snap.fault)
    mode_v = core_mode_value(snap.core_mode) or str(snap.core_mode)
    level = "ERR" if (estop_v or fault_v) else ("WARN" if age_facts.stale else "OK")
    return level, estop_v, fault_v, mode_v


def compute_reset_denied(*, state: BirdsEyeAxisDetailStateLike) -> tuple[dict[str, int], int]:
    reset_denied_by_axis = {
        str(axis_id): int(count)
        for axis_id, count in state.estop_reset_denied_count_by_axis.items()
        if str(axis_id).strip()
    }
    reset_denied_total = sum(reset_denied_by_axis.values())
    return reset_denied_by_axis, reset_denied_total


def _axis_local_motion_allowed(state: BirdsEyeAxisDetailStateLike, axis_id: str) -> bool:
    gate = state.core_axis_gate.get(axis_id)
    if gate is None:
        return False

    key_mode = str(gate.get("key_mode") or "").upper()
    if key_mode not in ("", "KEY0"):
        return False

    return (
        bool(gate.get("in_scope", False))
        and not bool(gate.get("missing", False))
        and not bool(gate.get("stale", False))
        and not bool(gate.get("hard_estop_active", False))
        and not bool(gate.get("fault_estop_active", False))
        and bool(gate.get("ready", False))
    )


def build_motion_facts(
    *,
    snap: BirdsEyeSnapLike,
    state: BirdsEyeAxisDetailStateLike,
    router: BirdsEyeRouterLike | None,
    axis_ids: Sequence[str],
    last_intents_meta: LastIntentsMetaLike,
) -> BirdsEyeMotionFacts:
    intents_types = last_intents_meta.get("types", []) or []
    intents_types_str = ",".join(str(t) for t in intents_types)
    reset_denied_by_axis, reset_denied_total = compute_reset_denied(state=state)

    try:
        axes_snapshot, blocked_by, blocked_payload, cmd_frame = build_blocked_and_axes_snapshot(
            snap=snap,
            state=state,
            router=router,
            axis_ids=list(axis_ids),
        )
    except Exception:
        axes_snapshot = []
        blocked_by = []
        blocked_payload = []
        cmd_frame = None

    joy = state.joy
    jf = extract_joy_facts(joy)
    joy_dm = bool(jf.deadman)
    joy_sel = bool(jf.select_hip)
    selected_lanes = _as_str_list(joy.selected_axes) if joy is not None else []

    attached_lanes = sorted(
        f"{axis_id}:{owner}" for axis_id, owner in state.axis_claims.items() if str(owner).strip()
    )

    resolved_moving_targets: list[str] = []
    if cmd_frame is not None:
        resolved_moving_targets = sorted(
            str(axis_id) for axis_id, sp in cmd_frame.axes.items() if abs(_as_float(sp.vel)) > 1e-9
        )

    local_manual_axes = [
        axis_id
        for axis_id in selected_lanes
        if axis_id in axis_ids and _axis_local_motion_allowed(state, axis_id)
    ]

    devices = sorted(str(k) for k in snap.densis.keys())

    return BirdsEyeMotionFacts(
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
