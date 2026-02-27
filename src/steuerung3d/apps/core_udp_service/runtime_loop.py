from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.command_frame import CommandFrame, coerce_param_ops
from steuerung3d.core.state import MachineState
from steuerung3d.core.mode_aggregate import aggregate_core_mode
from steuerung3d.core.telemetry import TelemetrySnapshot, apply_measured_snapshot
from steuerung3d.core.net import parse_hostport
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.axis_router import AxisRouter
from steuerung3d.protocol.udp_channels import UdpIntentIn, UdpTelemetryOut, UdpTelemetryFanout
from steuerung3d.protocol.udp_plc_channels import UdpPlcTelemetryIn, UdpPlcCommandOut
from steuerung3d.util.heartbeat import ChangeTracker

from .cli_validation import (
    uniq_axes_or_error,
    validate_dev_cmd_targets,
    validate_ui_telem_targets,
)
from .facts_builder import build_aggregate_inputs
from .fatal_ui import fatal as _fatal
from .reporter import emit_birds_eye_status, log_periodic_heartbeat
from .targets import expand_dev_cmd_targets as _expand_dev_cmd_targets
from .targets import expand_targets as _expand_targets

log = logging.getLogger("core_udp_service")
# Export helpers for CLI tests
__all__ = [
    "run_core_udp_service",
    "_expand_targets",
    "_expand_dev_cmd_targets",
]



def run_core_udp_service(*, args, status) -> int:
    # --- UDP endpoints ---
    intent_in_bind = parse_hostport(args.intent_in)

    op_intent_in = UdpIntentIn.bind(intent_in_bind)

    # UI telemetry targets
    if args.ui_telem_disable and (
        args.ui_telem_target
        or args.ui_telem_base is not None
        or int(args.ui_telem_count) > 0
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
            _expand_dev_cmd_targets(str(args.dev_cmd_base), int(args.dev_cmd_count), args.dev_cmd_host)
        )

        # Guard against accidental port overlap (common on Windows).
        if dev_telem_bind[0] == "127.0.0.1" and dev_telem_bind[1] in range(base, base + int(args.dev_cmd_count)):
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
    last_intents_meta = {
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
    t_last_report = t0

    # Track key state transitions (avoid log spam while still giving operators context).
    state_ch = ChangeTracker()

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
    )
    if err:
        return _fatal(err)

    axis_ui_outs = {axis_id: op_telem_outs[i] for i, axis_id in enumerate(axis_ids)} if op_telem_outs else {}
    for a in axis_ids:
        st.ensure_axis(a)

    router = AxisRouter(
        axis_ids=axis_ids,
        dev_cmd_out_by_axis=axis_cmd_outs,
        ui_telem_out_by_axis=axis_ui_outs,
    )

    def drain_intents():
        ints = op_intent_in.drain_intents(limit=200)
        if ints:
            stats["intents_in"] += len(ints)
            last_seen["intent_ts"] = time.monotonic()
            try:
                last_intents_meta["count"] = int(len(ints))
                last_intents_meta["types"] = sorted({type(i).__name__ for i in ints})
            except Exception:
                last_intents_meta["count"] = int(len(ints))
                last_intents_meta["types"] = []
            log.debug("rx intents: %d (last=%s)", len(ints), type(ints[-1]).__name__)
        return ints

    def device_step(state, cmd_frame, dt):
        nonlocal t_last_report

        # Per-axis command routing (no broadcast). Router reduces multi-axis frames.
        multi_axis = len(axis_ids) > 1
        if multi_axis:
            estop_reset_by_axis = dict(getattr(state, "estop_reset_req_by_axis", {}) or {})
            param_ops_by_axis = {k: coerce_param_ops(v) for k, v in dict(getattr(state, "pending_param_ops_by_axis", {}) or {}).items()}
        else:
            axis0 = axis_ids[0]
            estop_reset_by_axis = {
                axis0: bool(dict(getattr(state, "estop_reset_req_by_axis", {}) or {}).get(axis0, False) or getattr(state, "estop_reset_req", False))
            }
            per_axis_ops = coerce_param_ops(dict(getattr(state, "pending_param_ops_by_axis", {}) or {}).get(axis0, []))
            global_ops = coerce_param_ops(getattr(state, "pending_param_ops", []) or [])
            param_ops_by_axis = {axis0: (per_axis_ops or global_ops)}

        sent = router.publish_command_frames(
            cmd_frame,
            estop_reset_by_axis=estop_reset_by_axis,
            param_ops_by_axis=param_ops_by_axis,
        )
        stats["cmd_out"] += max(1, sent)
        last_seen["cmd_ts"] = time.monotonic()

        snaps = dev_telem_in.drain_telemetry(limit=50)
        if snaps:
            stats["dev_telem_in"] += len(snaps)
            last_seen["dev_telem_ts"] = time.monotonic()
            # Update axis-scoped caches from all received device snapshots.
            router.ingest_device_telemetry(snaps)
            # Device-side measured telemetry can arrive from multiple sources
            # (e.g. one DenSi process per axis). Apply *all* snapshots so each
            # axis' measured/meta fields get updated, instead of only the most
            # recent datagram.
            for snap in snaps:
                apply_measured_snapshot(state, snap)
            log.debug(
                "rx dev telem: %d (last estop=%s fault=%s tick=%s)",
                len(snaps),
                snaps[-1].estop,
                snaps[-1].fault,
                snaps[-1].tick,
            )
        else:
            log.debug("rx dev telem: 0")

        # Aggregate core mode (single source of truth for birds-eye).
        try:
            inputs = build_aggregate_inputs(state=state, router=router, axis_ids=axis_ids, dt=dt)
            result = aggregate_core_mode(inputs)
            # Apply aggregation result explicitly (aggregator remains pure)
            state.core_mode = result.core_mode
            state.core_blocked_by = list(result.blocked_by)
            state.core_axis_gate = dict(result.axis_gate)
            state.core_motion_allowed = bool(result.motion_allowed)
        except Exception:
            log.exception("core mode aggregation failed")

        log.debug("tx cmd frame: tick=%s estop=%s fault=%s core_mode=%s",
                  cmd_frame.tick, cmd_frame.estop, cmd_frame.fault, cmd_frame.core_mode)

        now = time.monotonic()
        if now - t_last_report >= 1.0:
            log_periodic_heartbeat(
                log=log,
                now=now,
                t0=t0,
                state=state,
                stats=stats,
                last_seen=last_seen,
            )
            t_last_report = now

    # Lifetick tracing: log Core->UI device tick at most every 0.5s per axis.
    _lt_last_ui_log_s_by_axis: dict[str, float] = {}

    def on_snapshot(snap: TelemetrySnapshot):
        # Log key state changes once (helps a lot during field debugging).
        try:
            mode_v = str(getattr(snap, "core_mode", ""))
            estop_v = bool(getattr(snap, "estop", False))
            fault_v = bool(getattr(snap, "fault", False))
            rig_v = str(getattr(snap, "rig_mode", ""))
            if (
                state_ch.changed("core_mode", mode_v)
                or state_ch.changed("estop", estop_v)
                or state_ch.changed("fault", fault_v)
                or state_ch.changed("rig_mode", rig_v)
            ):
                log.info("state: core_mode=%s estop=%s fault=%s rig_mode=%s", mode_v, estop_v, fault_v, rig_v)

            claims = tuple(sorted(dict(getattr(st, "axis_claims", {}) or {}).items()))
            if state_ch.changed("claims", claims):
                log.info("claims: %s", dict(claims))

            pe = bool(getattr(st, "param_edit_active", False))
            pg = str(getattr(st, "param_edit_group", ""))
            if state_ch.changed("param_edit", (pe, pg)):
                log.info("param_edit: active=%s group=%s", pe, pg)
        except Exception:
            pass

        if not args.ui_telem_disable:
            # One HiP per axis: send a *sliced* snapshot to each UI target.
            router.publish_ui_snapshot(snap)

        if c2_fanout is not None:
            c2_fanout.publish_telemetry(snap)
            stats["c2_telem_out"] += max(1, len(c2_telem_outs))
            last_seen["c2_telem_ts"] = time.monotonic()

        # LIFETICK trace: Core -> HiP (TelemetrySnapshot.axes[axis].device_tick)
        for axis_id in axis_ids:
            try:
                ax = dict(getattr(snap, "axes", {}) or {}).get(axis_id)
                dev_tick = getattr(ax, "device_tick", None)
                now_s = time.monotonic()
                last_s = float(_lt_last_ui_log_s_by_axis.get(axis_id, 0.0))
                if dev_tick is not None and (now_s - last_s) >= 0.5:
                    _lt_last_ui_log_s_by_axis[axis_id] = now_s
                    log.debug("LIFETICK Core tx UI telem: axis=%s device_tick=%s", axis_id, int(dev_tick))
            except Exception:
                pass

        if not args.ui_telem_disable:
            stats["ui_telem_out"] += max(1, len(axis_ids))
            last_seen["ui_telem_ts"] = time.monotonic()

            log.debug("tx ui telem: tick=%s estop=%s fault=%s", snap.tick, snap.estop, snap.fault)

        # Structured heartbeat for supervisor birds-eye (PLC telemetry remains unchanged).
        emit_birds_eye_status(
            status=status,
            snap=snap,
            state=st,
            router=router,
            axis_ids=axis_ids,
            last_intents_meta=last_intents_meta,
            last_seen=last_seen,
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
