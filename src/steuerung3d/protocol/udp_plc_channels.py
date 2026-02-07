from __future__ import annotations

"""UDP channels for legacy TwinCAT semicolon-delimited PLC frames.

These are intentionally *not* JSON. They carry plain ASCII lines like:

    0;E;0;...;EOD\;...

The canonical field order is defined in :mod:`steuerung3d.protocol.legacy_plc`.
"""

from dataclasses import dataclass
from typing import List, Tuple

from steuerung3d.adapters.links.udp_link import UdpLink


def _to_bytes(line: str) -> bytes:
    # PLC traffic is ASCII-ish. Keep it permissive.
    if not line.endswith(";"):
        line = line + ";"
    return line.encode("utf-8", errors="replace")


def _from_bytes(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").strip("\x00\r\n ")


@dataclass
class UdpPlcTelemetryIn:
    link: UdpLink

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpPlcTelemetryIn":
        # target unused for rx
        return UdpPlcTelemetryIn(link=UdpLink(bind=addr, target=addr))

    def drain_lines(self, limit: int = 1000) -> List[str]:
        return [_from_bytes(b) for b in self.link.poll(limit=limit)]


@dataclass
class UdpPlcTelemetryOut:
    link: UdpLink

    @staticmethod
    def connect(target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)) -> "UdpPlcTelemetryOut":
        return UdpPlcTelemetryOut(link=UdpLink(bind=bind, target=target))

    def publish_line(self, line: str) -> None:
        self.link.send(_to_bytes(line))


    def publish_telemetry(self, payload) -> None:
        """Publish telemetry on the PLC wire.

        Accepts either:
          - a pre-serialized PLC telemetry line (str)
          - a TelemetrySnapshot-like object (has .tick)
          - a list/tuple of lines or snapshots (we send the first snapshot, or all lines)

        This is intentionally defensive to keep the system running during the
        transition from JSON telemetry to PLC semicolon telegrams.
        """
        if payload is None:
            return

        # If we received a batch, handle common cases.
        if isinstance(payload, (list, tuple)):
            if not payload:
                return
            # list of strings -> publish each
            if all(isinstance(x, str) for x in payload):
                for line in payload:
                    self.publish_line(line)
                return
            # list containing a single snapshot
            payload = payload[0]

        if isinstance(payload, str):
            self.publish_line(payload)
            return

        # Snapshot-like object: encode to PLC line.
        tick = getattr(payload, "tick", None)
        if tick is None:
            # Last resort: send string representation (debug-friendly)
            self.publish_line(str(payload))
            return

        # Import lazily to avoid circular imports at module import time.
        try:
            from steuerung3d.protocol.plc_wire import encode_plc_telemetry  # type: ignore
        except Exception:
            encode_plc_telemetry = None  # type: ignore

        if encode_plc_telemetry is None:
            self.publish_line(str(payload))
            return

        try:
            line = encode_plc_telemetry(payload)
        except Exception:
            self.publish_line(str(payload))
            return
        self.publish_line(line)


@dataclass
class UdpPlcCommandIn:
    link: UdpLink

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpPlcCommandIn":
        return UdpPlcCommandIn(link=UdpLink(bind=addr, target=addr))

    def drain_lines(self, limit: int = 1000) -> List[str]:
        return [_from_bytes(b) for b in self.link.poll(limit=limit)]


@dataclass
class UdpPlcCommandOut:
    link: UdpLink

    @staticmethod
    def connect(target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)) -> "UdpPlcCommandOut":
        return UdpPlcCommandOut(link=UdpLink(bind=bind, target=target))

    def publish_line(self, line: str) -> None:
        self.link.send(_to_bytes(line))
