from __future__ import annotations

import logging

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.axis_router import AxisRouter
from steuerung3d.protocol.core_runner import CoreRunner

from .cli_validation import uniq_axes_or_error, validate_dev_cmd_targets, validate_ui_telem_targets
from .fatal_ui import fatal as _fatal
from .runtime_handlers import DeviceStepper, SnapshotHandler, build_intent_drain
from .runtime_helpers import (
    apply_mode_aggregation as _apply_mode_aggregation,
    compute_one_shots_by_axis as _compute_one_shots_by_axis,
)
from .runtime_loop_types import CoreRuntimeSetup, CoreUdpServiceArgs, RuntimeStats, UdpEndpoints

log = logging.getLogger("core_udp_service")


def _prepare_axis_ids(*, args: CoreUdpServiceArgs) -> list[str] | int:
    axis_ids = [a.strip() for a in args.axis if a and a.strip()]
    if not axis_ids:
        axis_ids = ["X"]
    axis_ids, err = uniq_axes_or_error(axis_ids)
    if err:
        return _fatal(err)
    return axis_ids


def _build_router(
    *, args: CoreUdpServiceArgs, endpoints: UdpEndpoints, state: MachineState, axis_ids: list[str]
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


def build_runtime_components(
    *,
    args: CoreUdpServiceArgs,
    status: object,
    endpoints: UdpEndpoints,
    runtime_stats: RuntimeStats,
) -> CoreRuntimeSetup | int:
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
    return CoreRuntimeSetup(
        tb=tb,
        state=state,
        axis_ids=axis_ids,
        router=router,
        drain_intents=drain_intents,
        device_step=device_step,
        on_snapshot=on_snapshot,
        runner=runner,
    )
