from __future__ import annotations

import logging
import time
from typing import Any, Callable

from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import apply_measured_snapshot
from steuerung3d.protocol.axis_router import AxisRouter
from steuerung3d.protocol.udp_plc_channels import UdpPlcTelemetryIn

from .reporter import log_periodic_heartbeat


def publish_commands(
    *,
    router: AxisRouter,
    axis_ids: list[str],
    state: MachineState,
    cmd_frame: Any,
    stats: dict[str, int],
    last_seen: dict[str, Any],
    compute_one_shots_by_axis: Callable[..., Any],
) -> None:
    estop_reset_by_axis, param_ops_by_axis = compute_one_shots_by_axis(state, axis_ids)
    sent = router.publish_command_frames(
        cmd_frame,
        estop_reset_by_axis=estop_reset_by_axis,
        param_ops_by_axis=param_ops_by_axis,
    )
    stats["cmd_out"] += max(1, sent)
    last_seen["cmd_ts"] = time.monotonic()


def ingest_device_telemetry(
    *,
    dev_telem_in: UdpPlcTelemetryIn,
    router: AxisRouter,
    state: MachineState,
    stats: dict[str, int],
    last_seen: dict[str, Any],
    log: logging.Logger,
) -> None:
    snaps = dev_telem_in.drain_telemetry(limit=50)
    if snaps:
        stats["dev_telem_in"] += len(snaps)
        last_seen["dev_telem_ts"] = time.monotonic()
        router.ingest_device_telemetry(snaps)
        for snap in snaps:
            apply_measured_snapshot(state, snap)
        log.debug(
            "rx dev telem: %d (last estop=%s fault=%s tick=%s)",
            len(snaps),
            snaps[-1].estop,
            snaps[-1].fault,
            snaps[-1].tick,
        )
        return
    log.debug("rx dev telem: 0")


def apply_mode_aggregation(
    *,
    apply_mode_aggregation_fn: Callable[..., None],
    state: MachineState,
    router: AxisRouter,
    axis_ids: list[str],
    dt: float,
    log: logging.Logger,
) -> None:
    try:
        apply_mode_aggregation_fn(state, router=router, axis_ids=axis_ids, dt=dt)
    except Exception:
        log.exception("core mode aggregation failed")


def emit_heartbeat(
    *,
    now: float,
    t_last_report: float,
    t0: float,
    state: MachineState,
    stats: dict[str, int],
    last_seen: dict[str, Any],
    log: logging.Logger,
) -> float:
    if now - t_last_report >= 1.0:
        log_periodic_heartbeat(
            log=log,
            now=now,
            t0=t0,
            state=state,
            stats=stats,
            last_seen=last_seen,
        )
        return now
    return t_last_report
