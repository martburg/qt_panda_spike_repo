from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Protocol, Tuple

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.net import parse_hostport
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.axis_router import AxisRouter
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.udp_channels import (
    UdpControlContextOut,
    UdpIntentIn,
    UdpTelemetryFanout,
    UdpTelemetryOut,
)
from steuerung3d.protocol.udp_plc_channels import UdpPlcCommandOut, UdpPlcTelemetryIn

from .cli_validation import (
    uniq_axes_or_error,
    validate_dev_cmd_targets,
    validate_ui_telem_targets,
)
from .fatal_ui import fatal as _fatal
from .runtime_handlers import DeviceStepper, SnapshotHandler, build_intent_drain
from .runtime_helpers import (
    apply_mode_aggregation as _apply_mode_aggregation,
    compute_one_shots_by_axis as _compute_one_shots_by_axis,
)
from .targets import (
    expand_dev_cmd_targets as _expand_dev_cmd_targets,
    expand_targets as _expand_targets,
)

log = logging.getLogger("core_udp_service")
# Export helpers for CLI tests
__all__ = [
    "run_core_udp_service",
    "_expand_targets",
    "_expand_dev_cmd_targets",
]


class CoreUdpServiceArgs(Protocol):
    intent_in: str
    control_context_target: str
    ui_telem_disable: bool
    ui_telem_target: list[str]
    ui_telem_host: str
    ui_telem_base: str | None
    ui_telem_count: int
    ui_telem_mode: str
    c2_telem_target: list[str]
    c2_telem_host: str
    c2_telem_base: str | None
    c2_telem_count: int
    dev_telem_in: str
    dev_cmd_target: list[str]
    dev_cmd_host: str
    dev_cmd_base: str | None
    dev_cmd_count: int
    axis: list[str]
    dt: float


@dataclass(frozen=True)
class _UdpEndpoints:
    intent_in_bind: tuple[str, int]
    op_intent_in: UdpIntentIn
    control_context_out: UdpControlContextOut
    ui_telem_targets: list[tuple[str, int]]
    op_telem_outs: list[UdpTelemetryOut]
    c2_telem_targets: list[tuple[str, int]]
    c2_telem_outs: list[UdpTelemetryOut]
    c2_fanout: UdpTelemetryFanout | None
    dev_telem_bind: tuple[str, int]
    dev_telem_in: UdpPlcTelemetryIn
    dev_cmd_targets: list[tuple[str, int]]
    dev_cmd_outs: list[UdpPlcCommandOut]


@dataclass(frozen=True)
class _CoreRuntimeSetup:
    tb: Timebase
    state: MachineState
    axis_ids: list[str]
    router: AxisRouter
    drain_intents: object
    device_step: DeviceStepper
    on_snapshot: SnapshotHandler
    runner: CoreRunner


@dataclass(frozen=True)
class _RuntimeStats:
    stats: dict[str, int]
    last_intents_meta: dict[str, object]
    last_seen: dict[str, object]
    t0: float


def _build_udp_endpoints(*, args: CoreUdpServiceArgs) -> _UdpEndpoints | int:
    intent_in_bind = parse_hostport(args.intent_in)
    op_intent_in = UdpIntentIn.bind(intent_in_bind)
    control_context_out = UdpControlContextOut.connect(parse_hostport(args.control_context_target))

    if args.ui_telem_disable and (
        args.ui_telem_target or args.ui_telem_base is not None or int(args.ui_telem_count) > 0
    ):
        return _fatal("UI telemetry disabled but UI targets were provided.")

    ui_telem_targets = _expand_targets(
        args.ui_telem_target,
        base=args.ui_telem_base,
        count=int(args.ui_telem_count),
        base_host=args.ui_telem_host,
        default_target=None if args.ui_telem_disable else ("127.0.0.1", 51002),
    )
    op_telem_outs = [UdpTelemetryOut.connect(t) for t in ui_telem_targets]

    c2_telem_targets = _expand_targets(
        args.c2_telem_target,
        base=args.c2_telem_base,
        count=int(args.c2_telem_count),
        base_host=args.c2_telem_host,
        default_target=None,
    )
    c2_telem_outs = [UdpTelemetryOut.connect(t) for t in c2_telem_targets]
    c2_fanout = UdpTelemetryFanout(outs=c2_telem_outs) if c2_telem_outs else None

    dev_telem_bind = parse_hostport(args.dev_telem_in)
    dev_telem_in = UdpPlcTelemetryIn.bind(dev_telem_bind)
    dev_cmd_targets = _build_dev_cmd_targets(args=args, dev_telem_bind=dev_telem_bind)
    if isinstance(dev_cmd_targets, int):
        return dev_cmd_targets
    dev_cmd_outs = [UdpPlcCommandOut.connect(t) for t in dev_cmd_targets]

    return _UdpEndpoints(
        intent_in_bind=intent_in_bind,
        op_intent_in=op_intent_in,
        control_context_out=control_context_out,
        ui_telem_targets=ui_telem_targets,
        op_telem_outs=op_telem_outs,
        c2_telem_targets=c2_telem_targets,
        c2_telem_outs=c2_telem_outs,
        c2_fanout=c2_fanout,
        dev_telem_bind=dev_telem_bind,
        dev_telem_in=dev_telem_in,
        dev_cmd_targets=dev_cmd_targets,
        dev_cmd_outs=dev_cmd_outs,
    )


def _build_dev_cmd_targets(
    *, args: CoreUdpServiceArgs, dev_telem_bind: tuple[str, int]
) -> list[Tuple[str, int]] | int:
    dev_cmd_targets: List[Tuple[str, int]] = []
    for s in args.dev_cmd_target:
        dev_cmd_targets.append(parse_hostport(s))

    if args.dev_cmd_base is not None and int(args.dev_cmd_count) > 0:
        base = int(str(args.dev_cmd_base).strip())
        dev_cmd_targets.extend(
            _expand_dev_cmd_targets(
                str(args.dev_cmd_base), int(args.dev_cmd_count), args.dev_cmd_host
            )
        )
        if dev_telem_bind[0] == "127.0.0.1" and dev_telem_bind[1] in range(
            base, base + int(args.dev_cmd_count)
        ):
            return _fatal(
                f"dev telemetry bind port {dev_telem_bind[1]} overlaps dev-cmd ports {base}..{base + int(args.dev_cmd_count) - 1}. "
                f"Pick a different --dev-telem-in (e.g. 127.0.0.1:{base + 100}) or shift --dev-cmd-base."
            )

    if not dev_cmd_targets:
        if len([a for a in args.axis if a and str(a).strip()]) <= 1:
            return [("127.0.0.1", 52001)]
        return []
    return dev_cmd_targets


def _build_runtime_stats() -> _RuntimeStats:
    return _RuntimeStats(
        stats={
            "intents_in": 0,
            "dev_telem_in": 0,
            "ui_telem_out": 0,
            "c2_telem_out": 0,
            "cmd_out": 0,
        },
        last_intents_meta={"count": 0, "types": []},
        last_seen={
            "intent_ts": None,
            "dev_telem_ts": None,
            "ui_telem_ts": None,
            "c2_telem_ts": None,
            "cmd_ts": None,
        },
        t0=time.monotonic(),
    )


def _log_startup_summary(*, args: CoreUdpServiceArgs, endpoints: _UdpEndpoints) -> None:
    log.info("=== core_udp_service starting ===")
    log.info("Operator: IntentIn  bind=%s", endpoints.intent_in_bind)
    if args.ui_telem_disable:
        log.info("Operator: TelemetryOut disabled")
    elif len(endpoints.ui_telem_targets) == 1:
        log.info("Operator: TelemetryOut target=%s", endpoints.ui_telem_targets[0])
    else:
        log.info("Operator: TelemetryOut targets=%s", endpoints.ui_telem_targets)
    if endpoints.c2_telem_targets:
        if len(endpoints.c2_telem_targets) == 1:
            log.info("Operator: C2 TelemetryOut target=%s", endpoints.c2_telem_targets[0])
        else:
            log.info("Operator: C2 TelemetryOut targets=%s", endpoints.c2_telem_targets)
    if len(endpoints.dev_cmd_targets) == 1:
        log.info("Device:   CommandOut target=%s", endpoints.dev_cmd_targets[0])
    else:
        log.info("Device:   CommandOut targets=%s", endpoints.dev_cmd_targets)
    log.info("Device:   TelemetryIn bind=%s", endpoints.dev_telem_bind)


def _prepare_axis_ids(*, args: CoreUdpServiceArgs) -> list[str] | int:
    axis_ids = [a.strip() for a in args.axis if a and a.strip()]
    if not axis_ids:
        axis_ids = ["X"]
    axis_ids, err = uniq_axes_or_error(axis_ids)
    if err:
        return _fatal(err)
    return axis_ids


def _build_router(
    *, args: CoreUdpServiceArgs, endpoints: _UdpEndpoints, state: MachineState, axis_ids: list[str]
) -> AxisRouter | int:
    err = validate_dev_cmd_targets(axis_ids=axis_ids, dev_cmd_targets=endpoints.dev_cmd_targets)
    if err:
        return _fatal(err)
    axis_cmd_outs = {axis_id: endpoints.dev_cmd_outs[i] for i, axis_id in enumerate(axis_ids)}

    err = validate_ui_telem_targets(
        ui_telem_disable=bool(args.ui_telem_disable),
        axis_ids=axis_ids,
        ui_telem_targets=endpoints.ui_telem_targets,
        mode=str(getattr(args, "ui_telem_mode", "per_axis") or "per_axis"),
    )
    if err:
        return _fatal(err)

    ui_mode = str(getattr(args, "ui_telem_mode", "per_axis") or "per_axis").strip().lower()
    axis_ui_outs = (
        {axis_id: endpoints.op_telem_outs[i] for i, axis_id in enumerate(axis_ids)}
        if (endpoints.op_telem_outs and ui_mode == "per_axis")
        else {}
    )
    for axis_id in axis_ids:
        state.ensure_axis(axis_id)
    return AxisRouter(
        axis_ids=axis_ids,
        dev_cmd_out_by_axis=axis_cmd_outs,
        ui_telem_out_by_axis=axis_ui_outs,
        ui_telem_fanout=list(endpoints.op_telem_outs) if ui_mode == "fanout" else [],
    )


def _build_runtime_components(
    *,
    args: CoreUdpServiceArgs,
    status: object,
    endpoints: _UdpEndpoints,
    runtime_stats: _RuntimeStats,
) -> _CoreRuntimeSetup | int:
    tb = Timebase(dt_s=args.dt)
    log.info("timebase dt = %.4fs", tb.dt_s)

    state = MachineState()
    axis_ids = _prepare_axis_ids(args=args)
    if isinstance(axis_ids, int):
        return axis_ids
    router = _build_router(args=args, endpoints=endpoints, state=state, axis_ids=axis_ids)
    if isinstance(router, int):
        return router

    drain_intents = build_intent_drain(
        op_intent_in=endpoints.op_intent_in,
        stats=runtime_stats.stats,
        last_seen=runtime_stats.last_seen,
        last_intents_meta=runtime_stats.last_intents_meta,
        log=log,
    )
    device_step = DeviceStepper(
        router=router,
        axis_ids=axis_ids,
        dev_telem_in=endpoints.dev_telem_in,
        stats=runtime_stats.stats,
        last_seen=runtime_stats.last_seen,
        t0=runtime_stats.t0,
        apply_mode_aggregation=_apply_mode_aggregation,
        compute_one_shots_by_axis=_compute_one_shots_by_axis,
        log=log,
    )
    on_snapshot = SnapshotHandler(
        router=router,
        axis_ids=axis_ids,
        args=args,
        c2_fanout=endpoints.c2_fanout,
        c2_telem_outs=endpoints.c2_telem_outs,
        control_context_out=endpoints.control_context_out,
        stats=runtime_stats.stats,
        last_seen=runtime_stats.last_seen,
        status=status,
        state=state,
        last_intents_meta=runtime_stats.last_intents_meta,
        log=log,
    )
    engine = CoreEngine(
        timebase=tb,
        state=state,
        drain_intents=drain_intents,
        handle_intent=apply_intent,
        device_step=device_step,
        on_snapshot=on_snapshot,
    )
    runner = CoreRunner(engine=engine, realtime=True)
    return _CoreRuntimeSetup(
        tb=tb,
        state=state,
        axis_ids=axis_ids,
        router=router,
        drain_intents=drain_intents,
        device_step=device_step,
        on_snapshot=on_snapshot,
        runner=runner,
    )


def _run_service_loop(*, runner: CoreRunner) -> int:
    runner.start()
    try:
        while runner.is_alive():
            runner.join(timeout=0.25)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt: stopping core runner...")
        runner.stop()
        runner.join(timeout=2.0)
        log.info("core runner stopped")
    return 0


def run_core_udp_service(*, args: CoreUdpServiceArgs, status: object) -> int:
    endpoints = _build_udp_endpoints(args=args)
    if isinstance(endpoints, int):
        return endpoints
    runtime_stats = _build_runtime_stats()
    _log_startup_summary(args=args, endpoints=endpoints)
    setup = _build_runtime_components(
        args=args,
        status=status,
        endpoints=endpoints,
        runtime_stats=runtime_stats,
    )
    if isinstance(setup, int):
        return setup
    return _run_service_loop(runner=setup.runner)
