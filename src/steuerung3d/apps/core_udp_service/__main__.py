from __future__ import annotations

import time
import logging

import argparse
import signal

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot, apply_measured_snapshot
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.udp_channels import (
    UdpIntentIn, UdpTelemetryOut,
    UdpTelemetryIn, UdpCommandOut,
)

log = logging.getLogger("core_udp_service")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    ap.add_argument("--dt", type=float, default=0.1)
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("log level = %s", args.log_level.upper())

    # --- UDP endpoints ---
    op_intent_in = UdpIntentIn.bind(("127.0.0.1", 51001))
    op_telem_out = UdpTelemetryOut.connect(("127.0.0.1", 51002))

    dev_telem_in = UdpTelemetryIn.bind(("127.0.0.1", 52002))
    dev_cmd_out  = UdpCommandOut.connect(("127.0.0.1", 52001))

    stats = {
        "intents_in": 0,
        "dev_telem_in": 0,
        "ui_telem_out": 0,
        "cmd_out": 0,
    }
    last_seen = {
        "intent_ts": None,
        "dev_telem_ts": None,
        "ui_telem_ts": None,
        "cmd_ts": None,
    }
    t0 = time.monotonic()
    t_last_report = t0

    log.info("=== core_udp_service starting ===")
    log.info("Operator: IntentIn  bind=%s", ("127.0.0.1", 51001))
    log.info("Operator: TelemetryOut target=%s", ("127.0.0.1", 51002))
    log.info("Device:   CommandOut target=%s", ("127.0.0.1", 52001))
    log.info("Device:   TelemetryIn bind=%s", ("127.0.0.1", 52002))

    # --- core state ---
    tb = Timebase(dt_s=args.dt)
    log.info("timebase dt = %.4fs", tb.dt_s)

    st = MachineState()
    st.ensure_axis("X")  # start small
    st.ensure_axis_cmd("X")

    def drain_intents():
        ints = op_intent_in.drain_intents(limit=200)
        if ints:
            stats["intents_in"] += len(ints)
            last_seen["intent_ts"] = time.monotonic()
            log.debug("rx intents: %d (last=%s)", len(ints), type(ints[-1]).__name__)
        return ints

    def device_step(state, cmd_frame, dt):
        nonlocal t_last_report

        dev_cmd_out.publish_command_frame(cmd_frame)
        stats["cmd_out"] += 1
        last_seen["cmd_ts"] = time.monotonic()

        snaps = dev_telem_in.drain_telemetry(limit=50)
        if snaps:
            stats["dev_telem_in"] += len(snaps)
            last_seen["dev_telem_ts"] = time.monotonic()
            apply_measured_snapshot(state, snaps[-1])  # <— you probably want this too

        if snaps:
            log.debug("rx dev telem: %d (estop=%s fault=%s tick=%s)",
                    len(snaps), snaps[-1].estop, snaps[-1].fault, snaps[-1].tick)
        else:
            log.debug("rx dev telem: 0")

        log.debug("tx cmd frame: tick=%s estop=%s fault=%s mode=%s",
                cmd_frame.tick, cmd_frame.estop, cmd_frame.fault, cmd_frame.mode)

        now = time.monotonic()
        if now - t_last_report >= 1.0:
            age_int = None if last_seen["intent_ts"] is None else now - last_seen["intent_ts"]
            age_dev = None if last_seen["dev_telem_ts"] is None else now - last_seen["dev_telem_ts"]
            age_cmd = None if last_seen["cmd_ts"] is None else now - last_seen["cmd_ts"]
            age_ui  = None if last_seen["ui_telem_ts"] is None else now - last_seen["ui_telem_ts"]

            log.info(
                "HB t=%.1fs intents=%d(age=%s) dev_telem=%d(age=%s) cmd_out=%d(age=%s) ui_telem_out=%d(age=%s)",
                now - t0,
                stats["intents_in"], "n/a" if age_int is None else f"{age_int:.2f}s",
                stats["dev_telem_in"], "n/a" if age_dev is None else f"{age_dev:.2f}s",
                stats["cmd_out"], "n/a" if age_cmd is None else f"{age_cmd:.2f}s",
                stats["ui_telem_out"], "n/a" if age_ui is None else f"{age_ui:.2f}s",
            )
            t_last_report = now

    def on_snapshot(snap: TelemetrySnapshot):
        op_telem_out.publish_telemetry(snap)
        stats["ui_telem_out"] += 1
        last_seen["ui_telem_ts"] = time.monotonic()

        log.debug("tx ui telem: tick=%s estop=%s fault=%s",
          snap.tick, snap.estop, snap.fault)

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

if __name__ == "__main__":
    raise SystemExit(main())
