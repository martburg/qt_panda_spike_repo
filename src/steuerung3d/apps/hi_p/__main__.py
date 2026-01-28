from __future__ import annotations

import argparse
import sys

import logging

from PySide6.QtWidgets import QApplication

from steuerung3d.apps.yellow.ui_shell import build_yellow_window
from steuerung3d.apps.yellow.controllers.hip_controller import HiPController
#from steuerung3d.protocol.transport import InMemTransport
from steuerung3d.protocol.udp_channels import UdpIntentOut, UdpTelemetryIn
# and import HiPController directly if you changed controllers/__init__.py:
from steuerung3d.apps.yellow.controllers.hip_controller import HiPController

log = logging.getLogger("hi_p")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=("ip",), default="ip")
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("log level = %s", args.log_level.upper())
    log.info("HI-P target IntentOut=%s  bind TelemetryIn=%s", ("127.0.0.1", 51001), ("127.0.0.1", 51002))


    app = QApplication(sys.argv)
    win = build_yellow_window(role="ip")

    intent_out = UdpIntentOut.connect(("127.0.0.1", 51001))
    telemetry_in = UdpTelemetryIn.bind(("127.0.0.1", 51002))

    ctl = HiPController(win=win, intent_out=intent_out, telemetry_in=telemetry_in)
    ctl.start_polling(period_ms=50)

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
