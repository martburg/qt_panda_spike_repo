"""Core UDP service runtime loop.

Stable public entrypoint for the core UDP service runtime.

This module keeps the public import surface stable while delegating directly to
this slice's owning modules:
- :mod:`runtime_loop_endpoints` for endpoint construction
- :mod:`runtime_loop_logging` for startup stats/logging and loop execution
- :mod:`runtime_loop_build` for runtime component assembly
"""

from __future__ import annotations

from .runtime_loop_build import build_runtime_components
from .runtime_loop_endpoints import build_udp_endpoints
from .runtime_loop_logging import build_runtime_stats, log_startup_summary, run_service_loop
from .runtime_loop_types import CoreUdpServiceArgs
from .targets import (
    expand_dev_cmd_targets as _expand_dev_cmd_targets,
    expand_targets as _expand_targets,
)

__all__ = [
    "run_core_udp_service",
    "_expand_targets",
    "_expand_dev_cmd_targets",
]


def run_core_udp_service(*, args: CoreUdpServiceArgs, status: object) -> int:
    """Build endpoints and runtime components, then run the core service loop."""
    endpoints = build_udp_endpoints(args=args)
    if isinstance(endpoints, int):
        return endpoints
    runtime_stats = build_runtime_stats()
    log_startup_summary(args=args, endpoints=endpoints)
    setup = build_runtime_components(
        args=args,
        status=status,
        endpoints=endpoints,
        runtime_stats=runtime_stats,
    )
    if isinstance(setup, int):
        return setup
    return run_service_loop(runner=setup.runner)
