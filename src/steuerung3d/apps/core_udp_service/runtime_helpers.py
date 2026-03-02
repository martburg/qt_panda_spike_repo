from __future__ import annotations

from steuerung3d.core.command_frame import coerce_param_ops
from steuerung3d.core.mode_aggregate import aggregate_core_mode
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.axis_router import AxisRouter

from .facts_builder import build_aggregate_inputs


def compute_one_shots_by_axis(
    state: MachineState, axis_ids: list[str]
) -> tuple[dict[str, bool], dict[str, list]]:
    """Compute per-axis one-shot signals for strict device routing.

    Returns:
        (estop_reset_by_axis, param_ops_by_axis)

    Notes:
    - Multi-axis: use per-axis maps directly.
    - Single-axis: preserve backward compatibility by allowing the legacy global
      fields to apply to the single configured axis.
    """
    multi_axis = len(axis_ids) > 1
    if multi_axis:
        estop_reset_by_axis = dict(getattr(state, "estop_reset_req_by_axis", {}) or {})
        per_axis_raw = dict(getattr(state, "pending_param_ops_by_axis", {}) or {})
        param_ops_by_axis = {k: coerce_param_ops(v) for k, v in per_axis_raw.items()}
        return estop_reset_by_axis, param_ops_by_axis

    axis0 = axis_ids[0]
    estop_reset_by_axis = {
        axis0: bool(
            dict(getattr(state, "estop_reset_req_by_axis", {}) or {}).get(axis0, False)
            or getattr(state, "estop_reset_req", False)
        )
    }
    per_axis_ops = coerce_param_ops(
        dict(getattr(state, "pending_param_ops_by_axis", {}) or {}).get(axis0, [])
    )
    global_ops = coerce_param_ops(getattr(state, "pending_param_ops", []) or [])
    param_ops_by_axis = {axis0: (per_axis_ops + global_ops)}
    return estop_reset_by_axis, param_ops_by_axis


def apply_mode_aggregation(
    state: MachineState, *, router: AxisRouter, axis_ids: list[str], dt: float
) -> None:
    """Compute and apply core mode aggregation (aggregator remains pure)."""
    inputs = build_aggregate_inputs(state=state, router=router, axis_ids=axis_ids, dt=dt)
    result = aggregate_core_mode(inputs)
    state.core_mode = result.core_mode
    state.core_blocked_by = list(result.blocked_by)
    state.core_axis_gate = dict(result.axis_gate)
    state.core_motion_allowed = bool(result.motion_allowed)
