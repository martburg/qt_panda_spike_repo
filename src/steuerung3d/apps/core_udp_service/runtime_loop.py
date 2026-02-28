"""Core UDP service runtime loop.

Public API wrapper.

This module re-exports the stable public surface from
:mod:`steuerung3d.apps.core_udp_service.runtime_loop_impl` so we can keep
imports stable while splitting implementation into smaller modules.
"""

from __future__ import annotations

from .runtime_loop_impl import run_core_udp_service, _expand_dev_cmd_targets, _expand_targets

__all__ = [
    "run_core_udp_service",
    "_expand_targets",
    "_expand_dev_cmd_targets",
]
