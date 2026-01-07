from __future__ import annotations

from typing import List, Protocol


class Link(Protocol):
    """
    Minimal 'wire link' seam.

    Anything that can:
      - send a datagram/frame as bytes
      - non-blockingly drain received datagrams/frames

    UDP is one implementation; later we can add ZMQ/TCP/NATS, etc.
    """

    def send(self, payload: bytes) -> None: ...
    def poll(self, limit: int = 100) -> List[bytes]: ...
    def close(self) -> None: ...
