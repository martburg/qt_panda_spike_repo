from __future__ import annotations

import logging
import time
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


def run_core_udp_service(*, args: CoreUdpServiceArgs, status: object) -> int:
    # --- UDP endpoints ---
    intent_in_bind = parse_hostport(args.intent_in)

    op_intent_in = UdpIntentIn.bind(intent_in_bind)

    control_context_out = UdpControlContextOut.connect(parse_hostport(args.control_context_target))

    # UI telemetry targets
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

    c2_telem_targets: List[Tuple[str, int]] = []
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

    # Device command broadcast targets (N DenSi apps each binding a unique command port)
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

        # Guard against accidental port overlap (common on Windows).
        if dev_telem_bind[0] == "127.0.0.1" and dev_telem_bind[1] in range(
            base, base + int(args.dev_cmd_count)
        ):
            return _fatal(
                f"dev telemetry bind port {dev_telem_bind[1]} overlaps dev-cmd ports {base}..{base + int(args.dev_cmd_count) - 1}. "
                f"Pick a different --dev-telem-in (e.g. 127.0.0.1:{base + 100}) or shift --dev-cmd-base."
            )

    if not dev_cmd_targets:
        # Default only for single-axis convenience. Multi-axis requires explicit per-axis targets.
        if len([a for a in args.axis if a and str(a).strip()]) <= 1:
            dev_cmd_targets = [("127.0.0.1", 52001)]
        else:
            dev_cmd_targets = []

    dev_cmd_outs = [UdpPlcCommandOut.connect(t) for t in dev_cmd_targets]

    stats = {
        "intents_in": 0,
        "dev_telem_in": 0,
        "ui_telem_out": 0,
        "c2_telem_out": 0,
        "cmd_out": 0,
    }
    last_intents_meta: dict[str, object] = {
        "count": 0,
        "types": [],
    }
    last_seen = {
        "intent_ts": None,
        "dev_telem_ts": None,
        "ui_telem_ts": None,
        "c2_telem_ts": None,
        "cmd_ts": None,
    }
    t0 = time.monotonic()

    log.info("=== core_udp_service starting ===")
    log.info("Operator: IntentIn  bind=%s", intent_in_bind)
    if args.ui_telem_disable:
        log.info("Operator: TelemetryOut disabled")
    elif len(ui_telem_targets) == 1:
        log.info("Operator: TelemetryOut target=%s", ui_telem_targets[0])
    else:
        log.info("Operator: TelemetryOut targets=%s", ui_telem_targets)
    if c2_telem_targets:
        if len(c2_telem_targets) == 1:
            log.info("Operator: C2 TelemetryOut target=%s", c2_telem_targets[0])
        else:
            log.info("Operator: C2 TelemetryOut targets=%s", c2_telem_targets)
    if len(dev_cmd_targets) == 1:
        log.info("Device:   CommandOut target=%s", dev_cmd_targets[0])
    else:
        log.info("Device:   CommandOut targets=%s", dev_cmd_targets)
    log.info("Device:   TelemetryIn bind=%s", dev_telem_bind)

    # --- core state ---
    tb = Timebase(dt_s=args.dt)
    log.info("timebase dt = %.4fs", tb.dt_s)

    st = MachineState()
    axis_ids = [a.strip() for a in args.axis if a and a.strip()]
    if not axis_ids:
        axis_ids = ["X"]

    # Router centralizes strict per-axis shaping (commands + UI snapshots)
    # and holds device-scoped caches used for axis-pinned UI values.

    axis_ids, err = uniq_axes_or_error(axis_ids)
    if err:
        return _fatal(err)

    # --- strict per-axis device command routing ---
    # We do NOT support broadcast device commands, because PLC code is frozen.
    err = validate_dev_cmd_targets(axis_ids=axis_ids, dev_cmd_targets=dev_cmd_targets)
    if err:
        return _fatal(err)

    # Map axis_id -> CommandOut transport (order matters).
    axis_cmd_outs = {axis_id: dev_cmd_outs[i] for i, axis_id in enumerate(axis_ids)}

    # --- strict per-axis UI telemetry routing ---
    err = validate_ui_telem_targets(
        ui_telem_disable=bool(args.ui_telem_disable),
        axis_ids=axis_ids,
        ui_telem_targets=ui_telem_targets,
        mode=str(getattr(args, "ui_telem_mode", "per_axis") or "per_axis"),
    )
    if err:
        return _fatal(err)

    ui_mode = str(getattr(args, "ui_telem_mode", "per_axis") or "per_axis").strip().lower()
    axis_ui_outs = (
        {axis_id: op_telem_outs[i] for i, axis_id in enumerate(axis_ids)}
        if (op_telem_outs and ui_mode == "per_axis")
        else {}
    )
    for a in axis_ids:
        st.ensure_axis(a)

    router = AxisRouter(
        axis_ids=axis_ids,
        dev_cmd_out_by_axis=axis_cmd_outs,
        ui_telem_out_by_axis=axis_ui_outs,
        ui_telem_fanout=list(op_telem_outs) if ui_mode == "fanout" else [],
    )

    drain_intents = build_intent_drain(
        op_intent_in=op_intent_in,
        stats=stats,
        last_seen=last_seen,
        last_intents_meta=last_intents_meta,
        log=log,
    )

    device_step = DeviceStepper(
        router=router,
        axis_ids=axis_ids,
        dev_telem_in=dev_telem_in,
        stats=stats,
        last_seen=last_seen,
        t0=t0,
        apply_mode_aggregation=_apply_mode_aggregation,
        compute_one_shots_by_axis=_compute_one_shots_by_axis,
        log=log,
    )

    on_snapshot = SnapshotHandler(
        router=router,
        axis_ids=axis_ids,
        args=args,
        c2_fanout=c2_fanout,
        c2_telem_outs=c2_telem_outs,
        control_context_out=control_context_out,
        stats=stats,
        last_seen=last_seen,
        status=status,
        state=st,
        last_intents_meta=last_intents_meta,
        log=log,
    )

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=drain_intents,
        handle_intent=apply_intent,
        device_step=device_step,
        on_snapshot=on_snapshot,
    )

    runner = CoreRunner(engine=eng, realtime=True)
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
