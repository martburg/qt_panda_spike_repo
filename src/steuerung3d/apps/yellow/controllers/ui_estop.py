"""Shim: re-export Qt-free E-Stop UI helpers from domain."""

from __future__ import annotations

from ..domain.ui_estop import (
    DotSpec,
    compute_estop_dot_state,
    compute_estop_dot_states,
    compute_header_estop_dot_states,
    age_to_online_state,
    infer_estop_profile,
    active_estop_keys_for_profile,
)

__all__ = [
    "DotSpec",
    "compute_estop_dot_state",
    "compute_estop_dot_states",
    "compute_header_estop_dot_states",
    "age_to_online_state",
    "infer_estop_profile",
    "active_estop_keys_for_profile",
]