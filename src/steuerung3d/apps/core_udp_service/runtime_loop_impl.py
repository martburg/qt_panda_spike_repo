from __future__ import annotations

from .runtime_loop_support import (
    CoreUdpServiceArgs,
    build_runtime_components,
    build_runtime_stats,
    build_udp_endpoints,
    log_startup_summary,
    run_service_loop,
)
from .targets import (
    expand_dev_cmd_targets as _expand_dev_cmd_targets,
    expand_targets as _expand_targets,
)

# Export helpers for CLI tests
__all__ = [
    "run_core_udp_service",
    "_expand_targets",
    "_expand_dev_cmd_targets",
]


def run_core_udp_service(*, args: CoreUdpServiceArgs, status: object) -> int:
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
