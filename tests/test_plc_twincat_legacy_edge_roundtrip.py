from __future__ import annotations

import socket
import time

from steuerung3d.adapters.plc_twincat_legacy.edge import TwinCATLegacyWinchEdge
from steuerung3d.adapters.plc_twincat_legacy.udp_sim import TwinCATLegacyPlcUdpSim
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.protocol.udp_channels import UdpCommandOut, UdpTelemetryIn
from steuerung3d.protocol.udp_transport_v2 import UdpTransportV2
from steuerung3d.protocol.udp_channels import UdpCommandIn, UdpTelemetryOut


def _free_udp_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return int(port)


def test_edge_roundtrip_with_udp_sim():
    # --- PLC sim endpoint ---
    plc_port = _free_udp_port()
    plc = TwinCATLegacyPlcUdpSim(axis_id="Anton", bind=("127.0.0.1", plc_port), dt_s=0.01)
    plc.start()

    # --- internal transport seam ---
    cmd_port = _free_udp_port()
    telem_port = _free_udp_port()

    cmd_out = UdpCommandOut.connect(("127.0.0.1", cmd_port))
    telem_in = UdpTelemetryIn.bind(("127.0.0.1", telem_port))

    tr = UdpTransportV2(
        cmd_in=UdpCommandIn.bind(("127.0.0.1", cmd_port)),
        telem_out=UdpTelemetryOut.connect(("127.0.0.1", telem_port)),
    )

    edge = TwinCATLegacyWinchEdge(
        axis_id="Anton",
        transport=tr,
        plc_remote=("127.0.0.1", plc_port),
        local_bind=("127.0.0.1", _free_udp_port()),
        dt_s=0.01,
        timeout_s=0.1,
    )

    try:
        # Send a command frame: enable + vel
        cmd = CommandFrame(
            tick=100,
            t_s=1.0,
            estop=False,
            fault=False,
            mode="LIVE",
            axes={"Anton": AxisSetpoint(enable=True, vel=1.0)},
            lifetick_echo={"Anton": 4242},
        )
        cmd_out.publish_command_frame(cmd)

        # Run edge a couple times to allow udp round-trip
        for _ in range(5):
            edge.step_once()
            time.sleep(0.01)

        snaps = telem_in.drain_telemetry(limit=50)
        assert snaps, "expected at least one telemetry snapshot"
        snap = snaps[-1]
        assert "Anton" in snap.axes
        ax = snap.axes["Anton"]

        # The PLC sim uses commanded speed as SpeedIstUI when enabled.
        assert abs(ax.vel - 1.0) < 1e-6
        assert ax.enabled is True
        assert ax.device_tick != 0

    finally:
        edge.close()
        plc.stop()
