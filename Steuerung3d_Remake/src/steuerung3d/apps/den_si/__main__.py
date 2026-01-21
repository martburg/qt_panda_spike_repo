from __future__ import annotations

import argparse
import sys
import logging

from PySide6.QtWidgets import QApplication

from steuerung3d.apps.yellow.ui_shell import build_yellow_window
from steuerung3d.apps.yellow.controllers.densi_controller import DenSiController
#from steuerung3d.protocol.transport import InMemTransport
from steuerung3d.protocol.udp_channels import UdpCommandIn, UdpTelemetryOut
from steuerung3d.apps.yellow.controllers.densi_controller import DenSiController

log = logging.getLogger("den_si") 

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=("cfc",), default="cfc")   # if you already parse role, keep yours
    ap.add_argument("--axis", action="append", default=["X"])
    ap.add_argument("--dt", type=float, default=0.01)
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    logging.basicConfig(
    level=getattr(logging, args.log_level.upper()),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
    log.info("log level = %s", args.log_level.upper())
    log.info("Den-Si bind CommandIn=%s  target TelemetryOut=%s", ("127.0.0.1", 52001), ("127.0.0.1", 52002))

    app = QApplication(sys.argv)
    win = build_yellow_window(role="cfc")

    command_in = UdpCommandIn.bind(("127.0.0.1", 52001))
    telemetry_out = UdpTelemetryOut.connect(("127.0.0.1", 52002))

    ctl = DenSiController(
        win=win,
        command_in=command_in,
        telemetry_out=telemetry_out,
        axis_ids=[a.strip() for a in args.axis if a.strip()],
        dt_s=args.dt,
    )
    ctl.start()

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
