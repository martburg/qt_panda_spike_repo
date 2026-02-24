from __future__ import annotations

import time
from typing import Dict, List

from steuerung3d.apps.yellow.domain.banner_facts import derive_banner_estate_from_word
from steuerung3d.core.core_mode import core_mode_value
from steuerung3d.core.joy_facts import extract_joy_facts
from steuerung3d.core.executor import build_command_frame
from steuerung3d.protocol.estop_bits import decode_estop_word


def log_periodic_heartbeat(*, log, now: float, t0: float, state, stats, last_seen) -> bool:
    age_int = None if last_seen["intent_ts"] is None else now - last_seen["intent_ts"]
    age_dev = None if last_seen["dev_telem_ts"] is None else now - last_seen["dev_telem_ts"]
    age_cmd = None if last_seen["cmd_ts"] is None else now - last_seen["cmd_ts"]
    age_ui = None if last_seen["ui_telem_ts"] is None else now - last_seen["ui_telem_ts"]
    age_c2 = None if last_seen["c2_telem_ts"] is None else now - last_seen["c2_telem_ts"]

    log.info(
        "HB t=%.1fs core_mode=%s rig=%s estop=%s fault=%s claims=%d | intents=%d(age=%s) dev_telem=%d(age=%s) cmd_out=%d(age=%s) ui_telem_out=%d(age=%s) c2_telem_out=%d(age=%s)",
        now - t0,
        core_mode_value(getattr(state, "core_mode", "")),
        getattr(state, "rig_mode", "DISCOVERY"),
        bool(getattr(state, "estop", False)),
        bool(getattr(state, "fault", False)),
        len(dict(getattr(state, "axis_claims", {}) or {})),
        stats["intents_in"], "n/a" if age_int is None else f"{age_int:.2f}s",
        stats["dev_telem_in"], "n/a" if age_dev is None else f"{age_dev:.2f}s",
        stats["cmd_out"], "n/a" if age_cmd is None else f"{age_cmd:.2f}s",
        stats["ui_telem_out"], "n/a" if age_ui is None else f"{age_ui:.2f}s",
        stats["c2_telem_out"], "n/a" if age_c2 is None else f"{age_c2:.2f}s",
    )
    return True


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
        age_dev = None if last_seen["dev_telem_ts"] is None else (now - float(last_seen["dev_telem_ts"]))
        age_cmd = None if last_seen["cmd_ts"] is None else (now - float(last_seen["cmd_ts"]))
        age_ui = None if last_seen["ui_telem_ts"] is None else (now - float(last_seen["ui_telem_ts"]))
        age_c2 = None if last_seen["c2_telem_ts"] is None else (now - float(last_seen["c2_telem_ts"]))

        estop_v = bool(getattr(snap, "estop", False))
        fault_v = bool(getattr(snap, "fault", False))
        mode_v = core_mode_value(getattr(state, "core_mode", "")) or str(getattr(snap, "core_mode", ""))

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

        axes_snapshot = []
        blocked_by = []
        blocked_payload = []
        try:
            cmd_frame = build_command_frame(state)
            cmd_axes = dict(getattr(cmd_frame, "axes", {}) or {})
            core_blocked = list(getattr(state, "core_blocked_by", []) or [])
            for item in core_blocked:
                code = str(getattr(item, "code", item))
                axis_id = getattr(item, "axis_id", None)
                detail = getattr(item, "detail", None)
                if axis_id:
                    blocked_by.append(f"{axis_id}:{code}")
                else:
                    blocked_by.append(code)
                blocked_payload.append(
                    {
                        "code": code,
                        "axis_id": axis_id,
                        "detail": detail,
                    }
                )

            axis_cmd = dict(getattr(state, "axis_cmd", {}) or {})
            axis_gate = dict(getattr(state, "core_axis_gate", {}) or {})
            for axis_id in axis_ids:
                estop_word = int(router.last_dev_estop_word_by_axis.get(axis_id, int(getattr(snap, "estop_status_word", 0)) or 0))
                bits = {}
                estate = ""
                try:
                    bits = decode_estop_word(estop_word)
                    estate = derive_banner_estate_from_word(estop_word, within_brake_grace=lambda: False)
                except Exception:
                    bits = {}
                    estate = ""

                armed = bool(str(estate).upper() in ("ARMED", "READY"))
                ready = bool(str(estate).upper() == "READY")

                cmd = axis_cmd.get(axis_id)
                cmd_out = cmd_axes.get(axis_id)
                cmd_enable = None
                cmd_vel = None
                if cmd_out is not None:
                    cmd_enable = bool(getattr(cmd_out, "enable", False))
                    try:
                        cmd_vel = float(getattr(cmd_out, "vel", 0.0) or 0.0)
                    except Exception:
                        cmd_vel = 0.0
                started = bool(cmd and (bool(getattr(cmd, "enable", False)) or abs(float(getattr(cmd, "vel", 0.0) or 0.0)) > 0.0))

                owner = str(state.axis_claims.get(axis_id, "") or "")
                if not owner:
                    holders = list(getattr(state, "lease_axis_holders", {}).get(axis_id, []) or [])
                    owner = str(holders[0]) if holders else ""

                reset_allowed = bool(owner) and bool(bits.get("reset_able", False))
                estop_axis = bool(str(estate).upper() == "ESTOP")
                fault_axis = bool(getattr(state, "fault", False))

                gate = dict(axis_gate.get(axis_id, {}) or {})
                gate_estop = gate.get("hard_estop_active")
                gate_fault = gate.get("fault_estop_active")
                gate_taster = gate.get("taster")
                gate_armed = gate.get("armed")
                gate_ready = gate.get("ready")
                gate_owner = gate.get("owner")
                gate_age_ms = gate.get("age_ms")
                gate_key_mode = gate.get("key_mode")
                if gate_owner:
                    owner = str(gate_owner)

                estop_axis = bool(gate_estop) if gate_estop is not None else bool(str(estate).upper() == "ESTOP")
                fault_axis = bool(gate_fault) if gate_fault is not None else bool(getattr(state, "fault", False))
                started = bool(started)
                armed = bool(gate_armed) if gate_armed is not None else bool(armed)
                ready = bool(gate_ready) if gate_ready is not None else bool(ready)

                axes_snapshot.append(
                    {
                        "axis_id": str(axis_id),
                        "in_scope": bool(gate.get("in_scope", True)),
                        "key_mode": str(gate_key_mode or ""),
                        "estop": bool(estop_axis),
                        "fault": bool(fault_axis),
                        "started": bool(started),
                        "cmd_enable": cmd_enable,
                        "cmd_vel": cmd_vel,
                        "taster_enabled": gate_taster,
                        "armed": bool(armed),
                        "ready": bool(ready),
                        "owner_hip_id": str(owner or ""),
                        "age_ms": gate_age_ms,
                        "reset_allowed": bool(reset_allowed),
                    }
                )
        except Exception:
            axes_snapshot = []
            blocked_by = []
            blocked_payload = []

        blocked_by = blocked_by[:3]
        blocked_summary = ",".join(blocked_by)

        joy = getattr(state, "joy", None)
        jf = extract_joy_facts(joy)
        joy_dm = bool(jf.deadman)
        joy_sel = bool(jf.select_hip)
        motion_allowed_i = int(bool(getattr(state, "core_motion_allowed", False)))
        summary = (
            f"core_mode={mode_v} motion_allowed={motion_allowed_i} blocked_by=[{blocked_summary}] "
            f"in=[{intents_types_str}] n={int(last_intents_meta.get('count', 0))} "
            f"reset_denied={int(reset_denied_total)}"
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
                "motion_allowed": bool(getattr(state, "core_motion_allowed", False)),
                "tick": int(getattr(snap, "tick", 0) or 0),
                "mode": str(mode_v),
                "estop": estop_v,
                "fault": fault_v,
                "intents_in_count": int(last_intents_meta.get("count", 0)),
                "intents_in_types": intents_types_str,
                "cmd_estop_reset": bool(getattr(cmd_frame, "estop_reset", False)),
                "cmd_resync": bool(getattr(cmd_frame, "resync", False)),
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
