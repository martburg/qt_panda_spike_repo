from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication

from steuerung3d.apps.yellow.controllers.densi_controller import DenSiController
from steuerung3d.apps.yellow.ui_shell import build_yellow_window
from steuerung3d.core.net import parse_hostport

# Default JSON channels (core/UI style)
from steuerung3d.protocol.udp_channels import UdpCommandIn, UdpTelemetryOut
from steuerung3d.util.app_bootstrap import bootstrap_logging

log = logging.getLogger("den_si")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=("cfc",), default="cfc")
    ap.add_argument(
        "--axis", action="append", default=[], help="Axis id(s). Typically exactly one for DenSi."
    )
    ap.add_argument("--dt", type=float, default=0.01)
    ap.add_argument(
        "--cmd-in",
        default="127.0.0.1:52001",
        help="UDP bind for CommandIn as host:port (default 127.0.0.1:52001).",
    )
    ap.add_argument(
        "--telem-out",
        default="127.0.0.1:52002",
        help="UDP target for TelemetryOut as host:port (default 127.0.0.1:52002).",
    )
    # NEW: explicit device wire protocol selector
    ap.add_argument(
        "--wire-proto",
        choices=("plc", "json"),
        default="plc",
        help="Device wire protocol for DenSi I/O. 'plc' = ; delimited telegrams, 'json' = internal snapshots.",
    )
    ap.add_argument("--config", default="", help="TOML config path for DenSi runtime.")

    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    axis_ids = [a.strip() for a in args.axis if a and a.strip()]
    if not axis_ids:
        axis_ids = ["X"]

    bootstrap_logging(
        role="den_si", axis=(axis_ids[0] if axis_ids else ""), log_level=args.log_level
    )
    log.info("log level = %s", str(args.log_level).upper())

    cmd_in_addr = parse_hostport(args.cmd_in)
    telem_out_addr = parse_hostport(args.telem_out)

    log.info(
        "Den-Si bind CommandIn=%s  target TelemetryOut=%s  wire_proto=%s",
        cmd_in_addr,
        telem_out_addr,
        args.wire_proto,
    )

    app = QApplication(sys.argv)
    win = build_yellow_window(role="cfc")

    axis_label = ",".join(axis_ids)
    try:
        win.setWindowTitle(
            f"HMI – DenSi ({axis_label})  cmd-in={cmd_in_addr[0]}:{cmd_in_addr[1]}  telem->{telem_out_addr[0]}:{telem_out_addr[1]}  wire={args.wire_proto}"
        )
    except Exception:
        pass

    # Choose channel implementations based on wire protocol.
    if args.wire_proto == "plc":
        from steuerung3d.protocol.udp_plc_channels import UdpPlcCommandIn, UdpPlcTelemetryOut

        command_in = UdpPlcCommandIn.bind(cmd_in_addr, axis_id=axis_ids[0] if axis_ids else None)
        telemetry_out = UdpPlcTelemetryOut.connect(telem_out_addr)
    else:
        command_in = UdpCommandIn.bind(cmd_in_addr)
        telemetry_out = UdpTelemetryOut.connect(telem_out_addr)

    ctl = DenSiController(
        win=win,
        command_in=command_in,
        telemetry_out=telemetry_out,
        axis_ids=axis_ids,
        dt_s=args.dt,
    )
    # Start controller (timer + IO loop)
    if hasattr(ctl, "start"):
        ctl.start()
    elif hasattr(ctl, "run"):
        ctl.run()
    else:
        raise AttributeError(f"DenSiController has no start/run method: {type(ctl).__name__}")

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
