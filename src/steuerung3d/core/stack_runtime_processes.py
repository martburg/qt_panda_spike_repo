"""StackSpec -> ProcessSpec expansion helpers.

Lane 1 refactor: pure helpers extracted from stack_runtime_impl.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

from .stack_render import make_context, render_argv
from .stack_spec import ProcessSpec, ServiceSpec, StackSpec


def service_args_with_config(svc: ServiceSpec) -> List[object]:
    """Return service args, adding '--config <path>' if present."""
    args: List[object] = list(getattr(svc, "args", []) or [])
    cfg = getattr(svc, "config", None)
    if cfg:
        args = list(args) + ["--config", str(cfg)]
    return args


def expand_processes(spec: StackSpec, *, session_dir: Path) -> List[ProcessSpec]:
    """Expand services into concrete process specs."""
    stack_ctx = {"name": spec.name}
    rig_ctx = {"axes": spec.axes, **(spec.rig or {})}
    net_ctx = dict(spec.net)

    processes: List[ProcessSpec] = []

    def add_process(name: str, argv: List[str], svc_env: Dict[str, str]):
        log_path = session_dir / f"{name}.log"
        processes.append(ProcessSpec(name=name, argv=argv, log_path=log_path, env=svc_env))

    for svc_key, svc in spec.services.items():
        if not svc.enabled:
            continue
        if not svc.module:
            raise ValueError(f"Service '{svc_key}' has no module")

        if svc.mode == "per_axis":
            for i, axis in enumerate(spec.axes):
                ctx = make_context(
                    stack=stack_ctx, net=net_ctx, rig=rig_ctx, axis=axis, axis_index=i
                )
                argv = [sys.executable, "-m", svc.module]
                argv += render_argv(service_args_with_config(svc), ctx)
                add_process(f"{svc_key}-{axis}", argv, dict(svc.env))
        else:
            # Single service instance, or an explicit pool.
            count = getattr(svc, "count", None)
            if isinstance(count, int) and count > 1:
                for i in range(int(count)):
                    ctx = make_context(
                        stack=stack_ctx, net=net_ctx, rig=rig_ctx, axis=None, axis_index=None
                    )
                    argv = [sys.executable, "-m", svc.module]
                    argv += render_argv(service_args_with_config(svc), ctx)
                    add_process(f"{svc_key}-{i + 1}", argv, dict(svc.env))
            else:
                ctx = make_context(
                    stack=stack_ctx, net=net_ctx, rig=rig_ctx, axis=None, axis_index=None
                )
                argv = [sys.executable, "-m", svc.module]
                argv += render_argv(service_args_with_config(svc), ctx)
                add_process(svc_key, argv, dict(svc.env))

    return processes
