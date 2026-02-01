from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# We only need uplink field order for indices
from steuerung3d.adapters.plc_twincat_legacy.codec import WINCH_UP_FIELDS


def _uplink_line(*, name: str, pos: float, vel: float, lifetick_tx: int = 0, enabled: bool = False) -> str:
    """Build a minimal valid uplink line: 38 prefix fields + EOD + tail."""
    prefix = ["0"] * len(WINCH_UP_FIELDS)  # should be 38

    def setf(field: str, value: str) -> None:
        i = WINCH_UP_FIELDS.index(field)
        prefix[i] = value

    STATUS_READY = 4356  # derived from ST: StatusnachUI == 4356 is treated as ready

    setf("OwnPID", "9999")
    setf("LifetickUItx", str(int(lifetick_tx) & 0xFFFF))
    setf("Status", str(STATUS_READY if enabled else 0))
    setf("GuideStatus", "0")
    setf("PosIst", f"{pos}")
    setf("SpeedIstUI", f"{vel}")
    setf("Name", name)
    setf("EStopStatus", "0")

    tail = ["SIM_TIME", "0", "0", "0", "0", "0", "0"]  # 7 tail fields
    return ";".join(prefix + ["EOD"] + tail) + ";"

@dataclass
class TwinCATLegacyPlcUdpSim:
    """Tiny UDP server that behaves like one PLC endpoint."""
    axis_id: str
    bind: Tuple[str, int]  # (ip, port) e.g. ("127.0.0.11", 15001)
    dt_s: float = 0.01

    _sock: Optional[socket.socket] = None
    _thread: Optional[threading.Thread] = None
    _stop: threading.Event = field(default_factory=threading.Event)

    # simple plant state
    pos: float = 0.0
    vel: float = 0.0
    # optional PLC->UI heartbeat (some variants increment this each loop)
    lifetick_tx: int = 0

    def start(self) -> None:
        if self._thread is not None:
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(self.bind)
        s.settimeout(0.2)
        self._sock = s

        def loop() -> None:
            assert self._sock is not None
            while not self._stop.is_set():
                try:
                    data, addr = self._sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    return

                line = data.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                parts = [p for p in line.split(";") if p != ""]
                # downlink fields we need:
                # 0 LifetickUIrx, 7 SpeedSollIN, 9 PosSoll, 5 ControlIN
                lifetick = int(parts[0]) if len(parts) > 0 else 0
                control_in = int(parts[5]) if len(parts) > 5 else 0
                speed_soll = float(parts[7]) if len(parts) > 7 else 0.0

                enable = (control_in != 0)

                # advance PLC heartbeat (millisecond granularity)
                self.lifetick_tx = (int(self.lifetick_tx) + int(self.dt_s * 1000)) & 0xFFFF

                # simple plant: follow vel when enabled
                self.vel = speed_soll if enable else 0.0
                self.pos += self.vel * self.dt_s

                reply = _uplink_line(
                    name=self.axis_id,
                    pos=self.pos,
                    vel=self.vel,
                    lifetick_tx=self.lifetick_tx,
                    enabled=enable,
                ).encode("utf-8")
                try:
                    self._sock.sendto(reply, addr)
                except OSError:
                    return

        self._thread = threading.Thread(target=loop, daemon=True, name=f"PlcUdpSim-{self.axis_id}")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=0.5)
            self._thread = None


import tomllib
from pathlib import Path
from typing import List

from steuerung3d.adapters.plc_twincat_legacy.device import TwinCATLegacyWinchUdpDevice
from steuerung3d.adapters.plc_twincat_legacy.fleet import TwinCATLegacyWinchFleetDevice


class _Bundle:
    def __init__(self, device, sims):
        self.device = device
        self._sims = sims

    def close(self) -> None:
        for s in self._sims:
            s.stop()
        close = getattr(self.device, "close", None)
        if callable(close):
            close()

    def step(self, state, cmd, dt: float) -> None:
        self.device.step(state, cmd, dt)


def build_udp_sim_fleet_from_toml(path: str | Path, *, dt_s: float = 0.01) -> _Bundle:
    cfg = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    root = cfg["device"]["plc_twincat_legacy_fleet"]
    defaults = root.get("defaults", {})
    remote_port = int(defaults.get("remote_port", 15001))

    axes = root["axes"]
    # Map each axis to a unique loopback IP so all can share port 15001
    # (Windows supports 127.0.0.x without extra config)
    base_octet = 11

    sims: List[TwinCATLegacyPlcUdpSim] = []
    devs: List[TwinCATLegacyWinchUdpDevice] = []

    for i, a in enumerate(axes):
        axis_id = str(a["axis_id"])
        local_port = int(a["local_port"])
        loop_ip = f"127.0.0.{base_octet + i}"

        sim = TwinCATLegacyPlcUdpSim(axis_id=axis_id, bind=(loop_ip, remote_port), dt_s=dt_s)
        sim.start()
        sims.append(sim)

        devs.append(
            TwinCATLegacyWinchUdpDevice(
                axis_id=axis_id,
                remote=(loop_ip, remote_port),      # pretend PLC is on loopback
                local=("127.0.0.1", local_port),    # bind locally on loopback
            )
        )

    return _Bundle(TwinCATLegacyWinchFleetDevice(devices=devs), sims)