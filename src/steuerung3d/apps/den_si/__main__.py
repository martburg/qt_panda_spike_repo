from __future__ import annotations

import argparse
import sys
import logging
from typing import Tuple

from steuerung3d.util.log_context import install_log_context

from PySide6.QtWidgets import QApplication

from steuerung3d.apps.yellow.ui_shell import build_yellow_window
from steuerung3d.apps.yellow.controllers.densi_controller import DenSiController
#from steuerung3d.protocol.transport import InMemTransport
from steuerung3d.protocol.udp_channels import UdpCommandIn, UdpTelemetryOut
from steuerung3d.apps.yellow.controllers.densi_controller import DenSiController

log = logging.getLogger("den_si") 


def _parse_hostport(s: str) -> Tuple[str, int]:
    """Parse 'host:port' (host may be omitted -> 127.0.0.1)."""
    s = (s or "").strip()
    if not s:
        raise ValueError("empty host:port")
    if s.count(":") == 0:
        # only port provided
        return ("127.0.0.1", int(s))
    host, port_s = s.rsplit(":", 1)
    host = host.strip() or "127.0.0.1"
    return (host, int(port_s))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=("cfc",), default="cfc")   # if you already parse role, keep yours
    # IMPORTANT: default must be empty when using action='append'. Otherwise argparse
    # will append onto the default list and you end up with phantom axes like "X,Debby".
    ap.add_argument("--axis", action="append", default=[], help="Axis id(s). Typically exactly one for DenSi.")
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
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    logging.basicConfig(
    level=getattr(logging, args.log_level.upper()),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
    # Provide consistent context fields on all log records (even if the format
    # doesn't include them yet).
    axis_ids = [a.strip() for a in args.axis if a and a.strip()] or ["X"]
    install_log_context(role="den_si", axis=axis_ids[0])
    log.info("log level = %s", args.log_level.upper())
    cmd_in_addr = _parse_hostport(args.cmd_in)
    telem_out_addr = _parse_hostport(args.telem_out)

    log.info("Den-Si bind CommandIn=%s  target TelemetryOut=%s", cmd_in_addr, telem_out_addr)

    app = QApplication(sys.argv)
    win = build_yellow_window(role="cfc")

    # Make the window self-identifying (axis + ports) to reduce integration confusion.
    axis_label = ",".join(axis_ids)
    try:
        win.setWindowTitle(
            f"HMI – DenSi ({axis_label})  cmd-in={cmd_in_addr[0]}:{cmd_in_addr[1]}  telem->{telem_out_addr[0]}:{telem_out_addr[1]}"
        )
    except Exception:
        pass

    command_in = UdpCommandIn.bind(cmd_in_addr)
    telemetry_out = UdpTelemetryOut.connect(telem_out_addr)

    ctl = DenSiController(
        win=win,
        command_in=command_in,
        telemetry_out=telemetry_out,
        axis_ids=axis_ids,
        dt_s=args.dt,
    )
    ctl.start()

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
