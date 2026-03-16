from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, List

from steuerung3d.ui.birdseye_format import LogTailer

from .run_dirs import make_session_dir
from .stack_preflight import cleanup_residual_bind_ports, extract_bind_ports
from .stack_render import make_context, render_argv
from .stack_runtime_meta import write_runtime_meta
from .stack_runtime_processes import (
    service_args_with_config as _service_args_with_config,
)
from .stack_spec import ProcessSpec
from .status import StatusCollector

if TYPE_CHECKING:
    from .stack_runtime_impl import StackRuntime


def discover_devices(rt: "StackRuntime", *, timeout_s: float) -> List[str]:
    if not rt.status:
        return []

    deadline = time.time() + max(0.1, float(timeout_s))
    last_devices: List[str] = []
    while time.time() < deadline:
        rt.status.poll()
        msg = rt.status.get("core", "")
        if msg:
            fields = msg.get("fields", {}) if isinstance(msg, dict) else {}
            devs = fields.get("devices")
            if isinstance(devs, list) and devs:
                last_devices = [str(x) for x in devs if str(x).strip()]
        time.sleep(0.05)
    out: List[str] = []
    seen = set()
    for d in last_devices:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def start_hips_real(rt: "StackRuntime") -> None:
    assert rt.session_dir is not None
    hip = rt.spec.services.get("hip")
    if not hip or not hip.enabled:
        return

    discovery_ms = int((rt.spec.rig or {}).get("discovery_ms") or 2000)
    devices = discover_devices(rt, timeout_s=discovery_ms / 1000.0)

    count = getattr(hip, "count", None)
    if isinstance(count, int):
        n_hips = max(1, int(count))
    else:
        n_hips = max(1, len(devices))

    stack_ctx = {"name": rt.spec.name}
    rig_ctx = {"axes": rt.spec.axes, **(rt.spec.rig or {})}
    net_ctx = dict(rt.spec.net)

    for i in range(n_hips):
        name = f"hip-{i + 1}"
        ctx = make_context(stack=stack_ctx, net=net_ctx, rig=rig_ctx, axis=None, axis_index=None)
        argv = [sys.executable, "-m", hip.module] + render_argv(_service_args_with_config(hip), ctx)
        p = ProcessSpec(
            name=name, argv=argv, log_path=rt.session_dir / f"{name}.log", env=dict(hip.env)
        )
        rt._spawn(p)
        time.sleep(0.05)


def start_runtime(rt: "StackRuntime") -> Path:
    base = rt.run_base / rt.spec.name
    rt.session_dir = make_session_dir(base, keep_last=rt.keep_last_sessions)

    status_in = (rt.spec.net or {}).get("status_in")
    if status_in:
        try:
            rt.status = StatusCollector(bind=str(status_in))
        except Exception:
            rt.status = None

    device_source = str((rt.spec.rig or {}).get("device_source") or "sim").strip().lower()

    spec_for_phase1 = rt.spec
    if device_source == "real":
        services = dict(rt.spec.services)
        if "densi" in services:
            services["densi"] = replace(services["densi"], enabled=False)
        if "hip" in services:
            services["hip"] = replace(services["hip"], enabled=False)
        spec_for_phase1 = replace(rt.spec, services=services)
    else:
        hip = rt.spec.services.get("hip")
        if hip and getattr(hip, "count", None) == "auto":
            services = dict(rt.spec.services)
            services["hip"] = replace(hip, count=max(1, len(rt.spec.axes)))
            spec_for_phase1 = replace(rt.spec, services=services)

    plan = rt.__class__.expand_processes_static(spec_for_phase1, session_dir=rt.session_dir)

    bind_ports = extract_bind_ports(plan)
    cleanup_residual_bind_ports(bind_ports)

    for p in plan:
        rt._spawn(p)
        time.sleep(0.05)

    if device_source == "real" and rt.spec.services.get("hip") and rt.spec.services["hip"].enabled:
        start_hips_real(rt)

    write_runtime_meta(rt, stopped_at_s=None)
    rt.tailers = {rp.spec.name: LogTailer(rp.spec.log_path) for rp in rt.processes}
    return rt.session_dir
