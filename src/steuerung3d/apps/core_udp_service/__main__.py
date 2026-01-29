from __future__ import annotations

import time
import logging

import argparse
import signal
from typing import Tuple, List

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


def _parse_hostport(s: str, default_host: str = "127.0.0.1") -> Tuple[str, int]:
    s = (s or "").strip()
    if not s:
        raise ValueError("empty host:port")
    if s.count(":") == 0:
        return (default_host, int(s))
    host, port_s = s.rsplit(":", 1)
    host = host.strip() or default_host
    return (host, int(port_s))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    ap.add_argument("--dt", type=float, default=0.02, help="Core tick (s)")
    ap.add_argument(
        "--axis",
        action="append",
        default=["X"],
        help="Axis ids to initialize in core state (repeatable). Example: --axis Anton --axis Debby",
    )
    ap.add_argument(
        "--dev-cmd-target",
        action="append",
        default=[],
        help=(
            "Device CommandOut target(s) as host:port. Repeatable. "
            "If not provided, defaults to 127.0.0.1:52001. "
            "Use this to broadcast command frames to multiple DenSi instances."
        ),
    )
    ap.add_argument(
        "--dev-cmd-base",
        default=None,
        help="Convenience: base port for Device CommandOut broadcast (e.g. 52001).",
    )
    ap.add_argument(
        "--dev-cmd-count",
        type=int,
        default=0,
        help="Convenience: number of Device CommandOut targets to generate from base port.",
    )

    # UI telemetry broadcast targets (multiple HiP windows)
    ap.add_argument(
        "--ui-telem-target",
        action="append",
        default=[],
        help=(
            "UI TelemetryOut target(s) as host:port. Repeatable. "
            "If not provided, defaults to 127.0.0.1:51002. "
            "Use this to broadcast telemetry to multiple HiP instances."
        ),
    )
    ap.add_argument(
        "--ui-telem-base",
        default=None,
        help="Convenience: base port for UI TelemetryOut broadcast (e.g. 51002).",
    )
    ap.add_argument(
        "--ui-telem-count",
        type=int,
        default=0,
        help="Convenience: number of UI TelemetryOut targets to generate from base port.",
    )
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("log level = %s", args.log_level.upper())

    # --- UDP endpoints ---
    op_intent_in = UdpIntentIn.bind(("127.0.0.1", 51001))

    # UI telemetry broadcast targets
    ui_telem_targets: List[Tuple[str, int]] = []
    for s in args.ui_telem_target:
        ui_telem_targets.append(_parse_hostport(s))
    if args.ui_telem_base is not None and int(args.ui_telem_count) > 0:
        base = int(str(args.ui_telem_base).strip())
        for i in range(int(args.ui_telem_count)):
            ui_telem_targets.append(("127.0.0.1", base + i))
    if not ui_telem_targets:
        ui_telem_targets = [("127.0.0.1", 51002)]
    op_telem_outs = [UdpTelemetryOut.connect(t) for t in ui_telem_targets]

    dev_telem_in = UdpTelemetryIn.bind(("127.0.0.1", 52002))

    # Device command broadcast targets (N DenSi apps each binding a unique command port)
    dev_cmd_targets: List[Tuple[str, int]] = []
    for s in args.dev_cmd_target:
        dev_cmd_targets.append(_parse_hostport(s))

    if args.dev_cmd_base is not None and int(args.dev_cmd_count) > 0:
        base = int(str(args.dev_cmd_base).strip())
        for i in range(int(args.dev_cmd_count)):
            dev_cmd_targets.append(("127.0.0.1", base + i))

    if not dev_cmd_targets:
        dev_cmd_targets = [("127.0.0.1", 52001)]

    dev_cmd_outs = [UdpCommandOut.connect(t) for t in dev_cmd_targets]

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
    if len(ui_telem_targets) == 1:
        log.info("Operator: TelemetryOut target=%s", ui_telem_targets[0])
    else:
        log.info("Operator: TelemetryOut broadcast targets=%s", ui_telem_targets)
    if len(dev_cmd_targets) == 1:
        log.info("Device:   CommandOut target=%s", dev_cmd_targets[0])
    else:
        log.info("Device:   CommandOut broadcast targets=%s", dev_cmd_targets)
    log.info("Device:   TelemetryIn bind=%s", ("127.0.0.1", 52002))

    # --- core state ---
    tb = Timebase(dt_s=args.dt)
    log.info("timebase dt = %.4fs", tb.dt_s)

    st = MachineState()
    axis_ids = [a.strip() for a in args.axis if a and a.strip()]
    if not axis_ids:
        axis_ids = ["X"]
    for a in axis_ids:
        st.ensure_axis(a)
        st.ensure_axis_cmd(a)

    def drain_intents():
        ints = op_intent_in.drain_intents(limit=200)
        if ints:
            stats["intents_in"] += len(ints)
            last_seen["intent_ts"] = time.monotonic()
            log.debug("rx intents: %d (last=%s)", len(ints), type(ints[-1]).__name__)
        return ints

    def device_step(state, cmd_frame, dt):
        nonlocal t_last_report

        # Broadcast command frame to all device endpoints.
        for tx in dev_cmd_outs:
            tx.publish_command_frame(cmd_frame)
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
        for tx in op_telem_outs:
            tx.publish_telemetry(snap)
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
