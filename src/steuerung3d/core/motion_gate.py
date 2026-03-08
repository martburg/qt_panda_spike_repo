from __future__ import annotations

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.state import MachineState


def axis_local_motion_allowed(state: MachineState, axis_id: str) -> bool:
    """Return whether *axis_id* may perform local/manual motion.

    This is intentionally **per-axis** and is used as an exception to the
    global core_mode gate for local single-axis motion. Group/synced motion
    remains governed by the existing global LIVE / rig-mode rules.

    Policy:
    - axis must be present in the aggregate gate map
    - axis must be in scope and effectively KEY0 eligible
    - axis must not be missing/stale
    - axis must not have active hard/fault estop causes
    - axis must be ready
    """

    axis_id = normalize_axis_id(axis_id)
    if not axis_id:
        return False

    gate = dict(getattr(state, "core_axis_gate", {}) or {}).get(axis_id)
    if not isinstance(gate, dict):
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
