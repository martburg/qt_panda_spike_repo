from __future__ import annotations

import socket
import threading
import time

from steuerung3d.adapters.plc_twincat_legacy.device import TwinCATLegacyWinchUdpDevice
from steuerung3d.core.command_frame import CommandFrame, AxisSetpoint
from steuerung3d.core.state import MachineState


def _make_uplink(pos: float, vel: float) -> bytes:
    # 38 prefix fields + EOD + 7 tail fields
    prefix = ["9999", "10", "0", "0", f"{pos}", f"{vel}"]  # OwnPID, tick, status, guidestatus, PosIst, SpeedIstUI
    # pad remaining prefix fields up to 38 total
    while len(prefix) < 38:
        prefix.append("0")
    tail = ["L_time", "0", "0", "0", "0", "0", "0"]
    return (";".join(prefix + ["EOD"] + tail) + ";").encode("utf-8")


def test_device_sends_every_frame_and_uses_cmd_tick_for_lifetick():
    received = {"lines": []}
    stop = threading.Event()

    # Fake PLC server
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    srv_port = srv.getsockname()[1]
    srv.settimeout(0.2)

    def server_loop():
        while not stop.is_set():
            try:
                data, addr = srv.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                # socket closed or invalid on Windows; exit thread cleanly
                return
            txt = data.decode("utf-8", errors="replace")
            received["lines"].append(txt)
            srv.sendto(_make_uplink(pos=1.0, vel=2.0), addr)

    th = threading.Thread(target=server_loop, daemon=True)
    th.start()

    dev = TwinCATLegacyWinchUdpDevice(
        axis_id="Anton",
        remote=("127.0.0.1", srv_port),
        local=("127.0.0.1", 0),  # ephemeral bind is OK for tests
        timeout_s=0.05,
    )

    st = MachineState()
    st.ensure_axis("Anton")

    # Frame 1: axis not present -> must still send lifetick (watchdog)
    cmd1 = CommandFrame(tick=100, t_s=0.0, estop=False, fault=False, mode="X", axes={})
    dev.step(st, cmd1, dt=0.01)

    # Frame 2: axis present -> sends again
    cmd2 = CommandFrame(
        tick=101, t_s=0.01, estop=False, fault=False, mode="X",
        axes={"Anton": AxisSetpoint(enable=True, vel=3.0)},
    )
    dev.step(st, cmd2, dt=0.01)

    # Give server a moment to receive both
    time.sleep(0.1)

    stop.set()
    th.join(timeout=0.5)
    dev.close()
    srv.close()

    assert len(received["lines"]) >= 2

    # First field is LifetickUIrx => should match cmd.tick & 0xFFFF
    first_pkt = received["lines"][0].strip()
    assert first_pkt.split(";")[0] == "100"

    second_pkt = received["lines"][1].strip()
    assert second_pkt.split(";")[0] == "101"
