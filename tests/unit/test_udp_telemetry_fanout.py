from __future__ import annotations

import socket
import time

from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.udp_channels import UdpTelemetryFanout, UdpTelemetryIn, UdpTelemetryOut


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _drain_until(rx: UdpTelemetryIn, timeout_s: float = 0.5) -> list[TelemetrySnapshot]:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        snaps = rx.drain_telemetry(limit=10)
        if snaps:
            return snaps
        time.sleep(0.01)
    return []


def test_udp_telemetry_fanout_delivers_to_two_targets() -> None:
    p1 = _free_port()
    p2 = _free_port()

    rx1 = UdpTelemetryIn.bind(("127.0.0.1", p1))
    rx2 = UdpTelemetryIn.bind(("127.0.0.1", p2))

    fanout = UdpTelemetryFanout(
        outs=[
            UdpTelemetryOut.connect(("127.0.0.1", p1)),
            UdpTelemetryOut.connect(("127.0.0.1", p2)),
        ]
    )

    snap = TelemetrySnapshot(tick=1, t_s=0.0, core_mode="IDLE", estop=False, fault=False, axes={})
    fanout.publish_telemetry(snap)

    got1 = _drain_until(rx1)
    got2 = _drain_until(rx2)

    assert got1, "first fanout target did not receive telemetry"
    assert got2, "second fanout target did not receive telemetry"


class _FailingOut:
    def publish_telemetry(self, _snap: TelemetrySnapshot) -> None:
        raise OSError("unreachable")


def test_udp_telemetry_fanout_continues_on_failure() -> None:
    p1 = _free_port()
    rx1 = UdpTelemetryIn.bind(("127.0.0.1", p1))

    outs = [UdpTelemetryOut.connect(("127.0.0.1", p1))]
    outs.extend(_FailingOut() for _ in range(7))

    fanout = UdpTelemetryFanout(outs=outs)
    snap = TelemetrySnapshot(tick=1, t_s=0.0, core_mode="IDLE", estop=False, fault=False, axes={})

    fanout.publish_telemetry(snap)

    got = _drain_until(rx1)
    assert got, "reachable fanout target did not receive telemetry"
