from __future__ import annotations

from steuerung3d.adapters.links.udp_link import UdpLink


def bind_udp_link(addr: tuple[str, int]) -> UdpLink:
    """Create the standard UDP receive link shape used across the repo."""
    return UdpLink(bind=addr, target=addr)


def connect_udp_link(
    target: tuple[str, int], *, bind: tuple[str, int] = ("127.0.0.1", 0)
) -> UdpLink:
    """Create the standard UDP transmit link shape used across the repo."""
    return UdpLink(bind=bind, target=target)
