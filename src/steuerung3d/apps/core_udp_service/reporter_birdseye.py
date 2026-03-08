from __future__ import annotations

import time
from typing import Dict, List

from steuerung3d.core.core_mode import core_mode_value
from steuerung3d.core.joy_facts import extract_joy_facts
from steuerung3d.core.motion_gate import axis_local_motion_allowed

from .reporter_axis_detail import build_blocked_and_axes_snapshot


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
        now = time.monotonic()
        age_int = None if last_seen["intent_ts"] is None else (now - float(last_seen["intent_ts"]))
        age_dev = (
            None if last_seen["dev_telem_ts"] is None else (now - float(last_seen["dev_telem_ts"]))
        )
        age_cmd = None if last_seen["cmd_ts"] is None else (now - float(last_seen["cmd_ts"]))
        age_ui = (
            None if last_seen["ui_telem_ts"] is None else (now - float(last_seen["ui_telem_ts"]))
        )
        age_c2 = (
            None if last_seen["c2_telem_ts"] is None else (now - float(last_seen["c2_telem_ts"]))
        )

        estop_v = bool(getattr(snap, "estop", False))
        fault_v = bool(getattr(snap, "fault", False))
        mode_v = core_mode_value(getattr(state, "core_mode", "")) or str(
            getattr(snap, "core_mode", "")
        )

        # Simple policy: ERR on estop/fault; WARN on stale inputs; else OK.
        stale = False
        for a in (age_int, age_dev):
            if a is not None and a > 2.0:
                stale = True
        level = "ERR" if (estop_v or fault_v) else ("WARN" if stale else "OK")

        intents_types = last_intents_meta.get("types", []) or []
        intents_types_str = ",".join([str(t) for t in intents_types])
        reset_denied_by_axis = dict(getattr(state, "estop_reset_denied_count_by_axis", {}) or {})
        reset_denied_total = 0
        try:
            reset_denied_total = sum(int(v) for v in reset_denied_by_axis.values())
        except Exception:
            reset_denied_total = 0

        axes_snapshot: list[dict[str, object]] = []
        blocked_by: list[str] = []
        blocked_payload: list[dict[str, object]] = []
        cmd_frame = None
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

        blocked_by = blocked_by[:3]
        blocked_summary = ",".join(blocked_by)

        joy = getattr(state, "joy", None)
        jf = extract_joy_facts(joy)
        joy_dm = bool(jf.deadman)
        joy_sel = bool(jf.select_hip)
        selected_lanes = (
            sorted(
                [str(x) for x in tuple(getattr(joy, "selected_axes", ()) or ()) if str(x).strip()]
            )
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
        motion_allowed_i = int(bool(getattr(state, "core_motion_allowed", False)))
        local_manual_axes = [
            axis_id
            for axis_id in selected_lanes
            if axis_id in axis_ids and axis_local_motion_allowed(state, axis_id)
        ]
        summary = (
            f"core_mode={mode_v} motion_allowed={motion_allowed_i} blocked_by=[{blocked_summary}] "
            f"local_manual=[{','.join(local_manual_axes)}] dm={int(joy_dm)} sel=[{','.join(selected_lanes)}] "
            f"moving=[{','.join(resolved_moving_targets)}] in=[{intents_types_str}] "
            f"n={int(last_intents_meta.get('count', 0))} reset_denied={int(reset_denied_total)}"
        )

        # Discovered devices (REAL) or spawned sims (SIM): expose as fields so the
        # supervisor can provision a HiP pool in REAL mode.
        try:
            densis = getattr(snap, "densis", {}) or {}
            devices = sorted([str(k) for k in densis.keys()])
        except Exception:
            devices = []

        status.emit_every(
            level=level,
            summary=summary,
            fields={
                "component": "core",
                "core_mode": str(mode_v),
                "blocked_by": list(blocked_payload),
                "joy_dm": bool(joy_dm),
                "joy_sel": bool(joy_sel),
                "deadman": bool(joy_dm),
                "selected_lanes": list(selected_lanes),
                "attached_lanes": list(attached_lanes),
                "resolved_moving_targets": list(resolved_moving_targets),
                "motion_allowed": bool(getattr(state, "core_motion_allowed", False)),
                "local_manual_axes": list(local_manual_axes),
                "local_manual_allowed": bool(local_manual_axes),
                "tick": int(getattr(snap, "tick", 0) or 0),
                "mode": str(mode_v),
                "estop": estop_v,
                "fault": fault_v,
                "intents_in_count": int(last_intents_meta.get("count", 0)),
                "intents_in_types": intents_types_str,
                "cmd_estop_reset": bool(getattr(cmd_frame, "estop_reset", False))
                if cmd_frame is not None
                else False,
                "cmd_resync": bool(getattr(cmd_frame, "resync", False))
                if cmd_frame is not None
                else False,
                "axes": axes_snapshot,
                "reset_denied_total": int(reset_denied_total),
                "reset_denied_by_axis": dict(reset_denied_by_axis),
                "devices": devices[:32],
                "devices_n": len(devices),
                "age_int_ms": None if age_int is None else age_int * 1000.0,
                "age_dev_ms": None if age_dev is None else age_dev * 1000.0,
                "age_cmd_ms": None if age_cmd is None else age_cmd * 1000.0,
                "age_ui_ms": None if age_ui is None else age_ui * 1000.0,
                "age_c2_ms": None if age_c2 is None else age_c2 * 1000.0,
            },
        )
    except Exception:
        return
