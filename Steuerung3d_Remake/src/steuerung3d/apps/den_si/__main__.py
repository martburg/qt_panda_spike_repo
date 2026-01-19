from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from steuerung3d.apps.yellow.ui_shell import build_yellow_window
from steuerung3d.apps.yellow.controllers import DenSiController
from steuerung3d.protocol.transport import InMemTransport


class CommandInPort:
    def __init__(self):
        # TODO: replace with real UDP CommandFrame receiver
        self._frames = []

    def drain_command_frames(self, limit: int = 1000):
        out = self._frames[:limit]
        self._frames = self._frames[limit:]
        return out


class TelemetryOutPort:
    def __init__(self, transport: InMemTransport):
        self.transport = transport

    def publish_telemetry(self, snap):
        self.transport.publish_telemetry(snap)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--axis", action="append", default=["X"], help="Axis ID (repeatable)")
    p.add_argument("--dt", type=float, default=0.01)
    args = p.parse_args()

    app = QApplication(sys.argv)
    win = build_yellow_window(role="cfc")

    # TODO (tomorrow): swap this stub with UDP device seam
    telem_bus = InMemTransport()

    ctl = DenSiController(
        win=win,
        command_in=CommandInPort(),
        telemetry_out=TelemetryOutPort(telem_bus),
        axis_ids=[str(a).strip() for a in args.axis if str(a).strip()],
        dt_s=args.dt,
    )
    ctl.start()

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
