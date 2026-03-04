from __future__ import annotations

from typing import Any, Dict, List, Tuple

from steuerung3d.apps.yellow.domain.banner_facts import derive_banner_estate_from_word
from steuerung3d.core.executor import build_command_frame
from steuerung3d.protocol.estop_bits import decode_estop_word


def build_blocked_and_axes_snapshot(
    *,
    snap: Any,
    state: Any,
    router: Any,
    axis_ids: List[str],
) -> Tuple[List[Dict[str, object]], List[str], List[Dict[str, object]], Any]:
    """Build per-axis status + blocked-by summary for birds-eye reporting.

    Returns:
        axes_snapshot, blocked_by, blocked_payload, cmd_frame

    NOTE: This is intentionally best-effort. Any unexpected failure should not
    take down the core supervisor loop.
    """

    axes_snapshot: List[Dict[str, object]] = []
    blocked_by: List[str] = []
    blocked_payload: List[Dict[str, object]] = []

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
        estop_word = int(
            router.last_dev_estop_word_by_axis.get(
                axis_id, int(getattr(snap, "estop_status_word", 0)) or 0
            )
        )

        bits: Dict[str, object] = {}
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

        started = bool(
            cmd
            and (
                bool(getattr(cmd, "enable", False))
                or abs(float(getattr(cmd, "vel", 0.0) or 0.0)) > 0.0
            )
        )

        owner = str(state.claim_owner(axis_id) or "")
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

        estop_axis = bool(gate_estop) if gate_estop is not None else estop_axis
        fault_axis = bool(gate_fault) if gate_fault is not None else fault_axis
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

    return axes_snapshot, blocked_by, blocked_payload, cmd_frame
