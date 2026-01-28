from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from steuerung3d.adapters.links.base import Link
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot

from .frame_slice import slice_command_frame
from .plc_codec import PlcCodec


@dataclass
class PlcEndpoint:
    """
    One PLC endpoint (e.g. Anton/Burt/Cecil/Debby).

    Owns:
      - one Link (UDP now, something else later)
      - one PlcCodec (meaning of bytes)
      - a set of axis_ids that this PLC is responsible for

    Provides:
      - send(): send full-state setpoints for owned axes
      - poll_latest(): drain RX and return latest valid telemetry snapshot
    """
    name: str
    axis_ids: list[str]
    link: Link
    codec: PlcCodec

    # diagnostics
    tx_count: int = 0
    rx_ok_count: int = 0
    rx_bad_count: int = 0
    last_rx_tick: Optional[int] = None

    def send(self, cmd: CommandFrame) -> None:
        sub = slice_command_frame(cmd, self.axis_ids)
        payload = self.codec.encode_command_frame(sub)
        self.link.send(payload)
        self.tx_count += 1

    def poll_latest(self, limit: int = 100) -> Optional[TelemetrySnapshot]:
        latest: Optional[TelemetrySnapshot] = None
        for dat in self.link.poll(limit=limit):
            snap = self.codec.try_decode_telemetry(dat)
            if snap is None:
                self.rx_bad_count += 1
                continue
            latest = snap
            self.rx_ok_count += 1

        if latest is not None:
            self.last_rx_tick = latest.tick
        return latest
