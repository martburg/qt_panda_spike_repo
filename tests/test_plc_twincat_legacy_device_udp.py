from __future__ import annotations

import socket
import threading
import time

from steuerung3d.adapters.plc_twincat_legacy.device import TwinCATLegacyWinchUdpDevice
from steuerung3d.core.command_frame import CommandFrame, AxisSetpoint
from steuerung3d.core.state import MachineState


def _make_uplink(pos: float, vel: float, *, enabled: bool = True, estop: bool = False) -> bytes:
    """
    Build a minimal valid uplink:
      - field 0 OwnPID
      - field 1 LifetickUItx
      - field 2 Status  (4356 == ready, derived from ST)
      - field 4 PosIst
      - field 5 SpeedIstUI
      - field 37 EStopStatus
    """
    STATUS_READY = "4356"
    status = STATUS_READY if enabled else "0"
    estop_status = "1" if estop else "0"

    # 38 prefix fields
    prefix = ["0"] * 38
    prefix[0] = "9999"      # OwnPID
    prefix[1] = "10"        # LifetickUItx (arbitrary for tests)
    prefix[2] = status      # Status
    prefix[3] = "0"         # GuideStatus
    prefix[4] = f"{pos}"    # PosIst
    prefix[5] = f"{vel}"    # SpeedIstUI
    prefix[37] = estop_status  # EStopStatus

    tail = ["L_time", "0", "0", "0", "0", "0", "0"]
    return (";".join(prefix + ["EOD"] + tail) + ";").encode("utf-8")



def test_device_sends_every_frame_and_echoes_last_uplink_lifetick():
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
    cmd1 = CommandFrame(tick=100, t_s=0.0, estop=False, fault=False, mode="X", axes={}, lifetick_echo={"Anton": 0})
    dev.step(st, cmd1, dt=0.01)

    # Frame 2: axis present -> sends again
    cmd2 = CommandFrame(
        tick=101, t_s=0.01, estop=False, fault=False, mode="X",
        axes={"Anton": AxisSetpoint(enable=True, vel=3.0)},
        lifetick_echo={"Anton": 10},
    )
    dev.step(st, cmd2, dt=0.01)

    # Give server a moment to receive both
    time.sleep(0.1)

    stop.set()
    th.join(timeout=0.5)
    dev.close()
    srv.close()

    assert len(received["lines"]) >= 2

    # First field is LifetickUIrx => must echo the last LifetickUItx we saw on uplink.
    # (On first packet we haven't received anything yet, so 0 is valid.)
    first_pkt = received["lines"][0].strip()
    assert first_pkt.split(";")[0] == "0"

    second_pkt = received["lines"][1].strip()
    assert second_pkt.split(";")[0] == "10"

def test_device_rebases_possoll_to_posist_on_enable_edge():
    received = {"lines": []}
    stop = threading.Event()

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
                return
            txt = data.decode("utf-8", errors="replace")
            received["lines"].append(txt)
            # Always respond with PosIst=1.0 so the device caches it into state
            srv.sendto(_make_uplink(pos=1.0, vel=0.0), addr)

    th = threading.Thread(target=server_loop, daemon=True)
    th.start()

    dev = TwinCATLegacyWinchUdpDevice(
        axis_id="Anton",
        remote=("127.0.0.1", srv_port),
        local=("127.0.0.1", 0),
        timeout_s=0.05,
    )

    st = MachineState()
    st.ensure_axis("Anton")

    # Step once with no command: still sends watchdog, and receives uplink -> caches ax.pos = 1.0
    cmd0 = CommandFrame(tick=1, t_s=0.0, estop=False, fault=False, mode="X", axes={})
    dev.step(st, cmd0, dt=0.01)

    # Now enable with nonzero vel. On enable edge, PosSoll must equal cached PosIst exactly (1.0),
    # not 1.0 + vel*dt.
    cmd1 = CommandFrame(
        tick=2, t_s=0.01, estop=False, fault=False, mode="X",
        axes={"Anton": AxisSetpoint(enable=True, vel=3.0)},
    )
    dev.step(st, cmd1, dt=0.01)

    time.sleep(0.1)
    stop.set()
    th.join(timeout=0.5)
    dev.close()
    srv.close()

    assert len(received["lines"]) >= 2
    pkt_enable = received["lines"][1].strip().split(";")

    # PosSoll is field index 9 in WINCH_DOWN_BASE_FIELDS
    pos_soll = float(pkt_enable[9])
    assert pos_soll == 1.0

def test_enabled_is_measured_not_commanded():
    received = {"lines": []}
    stop = threading.Event()

    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    srv_port = srv.getsockname()[1]
    srv.settimeout(0.2)

    # PLC always reports NOT READY (enabled=False) even if we command enable=True
    def server_loop():
        while not stop.is_set():
            try:
                data, addr = srv.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return
            txt = data.decode("utf-8", errors="replace")
            received["lines"].append(txt)
            srv.sendto(_make_uplink(pos=0.0, vel=0.0, enabled=False), addr)

    th = threading.Thread(target=server_loop, daemon=True)
    th.start()

    dev = TwinCATLegacyWinchUdpDevice(
        axis_id="Anton",
        remote=("127.0.0.1", srv_port),
        local=("127.0.0.1", 0),
        timeout_s=0.05,
    )

    st = MachineState()
    st.ensure_axis("Anton")

    # Command enable=True for a few frames to ensure we receive uplink
    for k in range(3):
        cmd = CommandFrame(
            tick=10 + k,
            t_s=0.01 * k,
            estop=False,
            fault=False,
            mode="X",
            axes={"Anton": AxisSetpoint(enable=True, vel=1.0)},
        )
        dev.step(st, cmd, dt=0.01)

    time.sleep(0.1)
    stop.set()
    th.join(timeout=0.5)
    dev.close()
    srv.close()

    # Measured truth: PLC says not enabled => must be False
    assert st.axes["Anton"].enabled is False

