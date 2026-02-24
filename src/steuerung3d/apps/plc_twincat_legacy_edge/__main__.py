from __future__ import annotations

import argparse
import logging
import time
from typing import Tuple

from steuerung3d.core.net import parse_hostport

from steuerung3d.util.log_context import install_log_context

from steuerung3d.protocol.udp_channels import UdpCommandIn, UdpTelemetryOut
from steuerung3d.protocol.udp_transport_v2 import UdpTransportV2

from steuerung3d.adapters.plc_twincat_legacy.edge import TwinCATLegacyWinchEdge

log = logging.getLogger("plc_twincat_legacy_edge")



def main() -> int:
    ap = argparse.ArgumentParser(prog="steuerung3d.apps.plc_twincat_legacy_edge")
    ap.add_argument("--axis", required=True, help="Axis id this PLC endpoint owns (e.g. Anton)")
    ap.add_argument("--dt", type=float, default=0.01)

    # internal TransportV2 seam
    ap.add_argument("--cmd-in", default="127.0.0.1:52001", help="bind host:port for CommandIn")
    ap.add_argument("--telem-out", default="127.0.0.1:52002", help="target host:port for TelemetryOut")

    # PLC wire endpoints
    ap.add_argument("--plc-remote", required=True, help="PLC remote host:port (usually <plc_ip>:15001)")
    ap.add_argument(
        "--local-bind",
        required=True,
        help="Local bind host:port for PLC socket (usually <controller_ip>:1500x)",
    )
    ap.add_argument("--timeout", type=float, default=0.02, help="UDP recv timeout seconds")

    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    install_log_context(role="plc_edge", axis=str(args.axis))

    axis_id = str(args.axis).strip()
    cmd_in = parse_hostport(args.cmd_in)
    telem_out = parse_hostport(args.telem_out)
    plc_remote = parse_hostport(args.plc_remote)
    local_bind = parse_hostport(args.local_bind)

    log.info(
        "starting axis=%s cmd_in=%s telem_out=%s plc_remote=%s local_bind=%s dt=%.4fs",
        axis_id,
        cmd_in,
        telem_out,
        plc_remote,
        local_bind,
        float(args.dt),
    )

    tr = UdpTransportV2(
        cmd_in=UdpCommandIn.bind(cmd_in),
        telem_out=UdpTelemetryOut.connect(telem_out),
    )

    edge = TwinCATLegacyWinchEdge(
        axis_id=axis_id,
        transport=tr,
        plc_remote=plc_remote,
        local_bind=local_bind,
        timeout_s=float(args.timeout),
        dt_s=float(args.dt),
    )

    dt = float(args.dt)
    next_t = time.monotonic()
    try:
        while True:
            edge.step_once()
            next_t += dt
            sleep_s = next_t - time.monotonic()
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                next_t = time.monotonic()
    except KeyboardInterrupt:
        return 0
    finally:
        edge.close()


if __name__ == "__main__":
    raise SystemExit(main())
