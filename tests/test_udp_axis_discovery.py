from __future__ import annotations

from typing import TYPE_CHECKING, cast

from steuerung3d.adapters.plc.udp_device import UdpPlcDevice
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.core.state import MachineState

if TYPE_CHECKING:
    from steuerung3d.adapters.plc.udp_device import UdpPlcDevice as _UdpPlcDeviceType


class FakeSock:
    def __init__(self, rx_bytes: bytes):
        self._rx = rx_bytes
        self.sent: list[tuple[bytes, tuple[str, int]]] = []

    def settimeout(self, value: float | None, /) -> None:
        return

    def sendto(self, data: bytes, addr: tuple[str, int], /) -> int | None:
        self.sent.append((data, addr))
        return len(data)

    def recvfrom(self, bufsize: int, /) -> tuple[bytes, tuple[str, int]]:
        return self._rx, ("127.0.0.1", 55001)

    def close(self) -> None:
        return


def test_udp_device_discovers_unknown_axis_from_telemetry():
    # Telemetry includes an axis not present in the outgoing CommandFrame ("Anton")
    telemetry = b"1;Anton;1;0.0;12.34;0;\n"
    dev = UdpPlcDevice(remote=("127.0.0.1", 55001))
    dev._sock = cast("_UdpPlcDeviceType._SockLike", FakeSock(telemetry))

    st = MachineState()
    st.tick = 1

    # We must send at least one axis in cmd, or UdpPlcDevice.step() returns early.
    cmd = CommandFrame(
        tick=1,
        t_s=0.0,
        estop=False,
        fault=False,
        core_mode="LIVE",
        axes={"X": AxisSetpoint(enable=True, vel=0.0)},
    )

    dev.step(st, cmd, dt=0.01)

    assert "Anton" in st.axes
    assert st.axes["Anton"].pos == 12.34
    assert st.axes["Anton"].enabled is True
    assert st.axes["Anton"].meta.get("last_seen_tick") == 1
