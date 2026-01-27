from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.adapters.plc.udp_device import UdpPlcDevice
from steuerung3d.core.command_frame import CommandFrame, AxisSetpoint
from steuerung3d.core.state import MachineState


class FakeSock:
    def __init__(self, rx_bytes: bytes):
        self._rx = rx_bytes
        self.sent = []

    def settimeout(self, _t: float) -> None:
        return

    def sendto(self, payload: bytes, remote):
        self.sent.append((payload, remote))

    def recvfrom(self, _n: int):
        return self._rx, ("127.0.0.1", 55001)

    def close(self):
        return


def test_udp_device_discovers_unknown_axis_from_telemetry():
    # Telemetry includes an axis not present in the outgoing CommandFrame ("Anton")
    telemetry = b"1;Anton;1;0.0;12.34;0;\n"
    dev = UdpPlcDevice(remote=("127.0.0.1", 55001))
    dev._sock = FakeSock(telemetry)

    st = MachineState()
    st.tick = 1

    # We must send at least one axis in cmd, or UdpPlcDevice.step() returns early.
    cmd = CommandFrame(axes={"X": AxisSetpoint(enable=True, vel=0.0)})

    dev.step(st, cmd, dt=0.01)

    assert "Anton" in st.axes
    assert st.axes["Anton"].pos == 12.34
    assert st.axes["Anton"].enabled is True
    assert st.axes["Anton"].meta.get("last_seen_tick") == 1
