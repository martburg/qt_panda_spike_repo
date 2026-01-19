from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from steuerung3d.apps.yellow.ui_shell import build_yellow_window
from steuerung3d.apps.yellow.controllers import HiPController
from steuerung3d.protocol.transport import InMemTransport


class IntentOutPort:
    def __init__(self, transport: InMemTransport):
        self.transport = transport

    def send_intent(self, intent):
        self.transport.publish_intent(intent)


class TelemetryInPort:
    def __init__(self, transport: InMemTransport):
        self.transport = transport

    def drain_telemetry(self, limit: int = 1000):
        return self.transport.drain_telemetry(limit=limit)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--replay", action="store_true", help="For now: run with an in-mem transport stub.")
    args = p.parse_args()

    app = QApplication(sys.argv)
    win = build_yellow_window(role="ip")

    # TODO (tomorrow): swap this stub with UDP operator seam
    transport = InMemTransport()

    ctl = HiPController(win=win, intent_out=IntentOutPort(transport), telemetry_in=TelemetryInPort(transport))
    ctl.start_polling(period_ms=50)

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
