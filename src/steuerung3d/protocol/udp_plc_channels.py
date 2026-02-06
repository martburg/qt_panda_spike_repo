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
