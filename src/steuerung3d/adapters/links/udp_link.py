from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class UdpLink:
    """
    Raw UDP link.

    - bind: local (host, port) to receive from PLC
    - target: remote (host, port) to send to PLC
    - poll(): non-blocking drain of available datagrams
    """

    bind: Tuple[str, int]
    target: Tuple[str, int]
    recv_buf: int = 65535

    def __post_init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # IMPORTANT (Windows): binding port 0 eagerly allocates a *real* local port.
        # If we do this for pure-TX channels, the OS may pick a port we want to
        # reserve for receivers (e.g. core dev-telemetry-in or DenSi command-in).
        # For TX links we pass bind=(host, 0); in that case do not bind at all.
        if self.bind[1] != 0:
            self.sock.bind(self.bind)
        self.sock.setblocking(False)

    def send(self, payload: bytes) -> None:
        self.sock.sendto(payload, self.target)

    def poll(self, limit: int = 100) -> List[bytes]:
        out: List[bytes] = []
        for _ in range(limit):
            try:
                data, _addr = self.sock.recvfrom(self.recv_buf)
            except BlockingIOError:
                break
            out.append(data)
        return out

    def close(self) -> None:
        self.sock.close()
