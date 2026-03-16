from __future__ import annotations

import logging
import time

from steuerung3d.protocol.core_runner import CoreRunner

from .runtime_loop_types import CoreUdpServiceArgs, RuntimeStats, UdpEndpoints

log = logging.getLogger("core_udp_service")


def build_runtime_stats() -> RuntimeStats:
    return RuntimeStats(
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


def log_startup_summary(*, args: CoreUdpServiceArgs, endpoints: UdpEndpoints) -> None:
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


def run_service_loop(*, runner: CoreRunner) -> int:
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
