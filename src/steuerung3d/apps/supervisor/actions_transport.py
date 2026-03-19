from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.protocol.udp_channels import UdpJsonIn, UdpJsonOut
from steuerung3d.protocol.udp_link_scaffold import bind_udp_link, connect_udp_link

from .models import DensiRemoteAction


@dataclass(frozen=True)
class UdpDensiActionIn:
    rx: UdpJsonIn[DensiRemoteAction]

    @staticmethod
    def bind(addr: tuple[str, int]) -> "UdpDensiActionIn":
        link = bind_udp_link(addr)
        return UdpDensiActionIn(rx=UdpJsonIn(link=link, decode=_decode_action))

    def drain_actions(self, limit: int = 1000) -> list[DensiRemoteAction]:
        return self.rx.drain(limit=limit)


@dataclass(frozen=True)
class UdpDensiActionOut:
    """UDP transport for remote densi actions.

    The public publish surface intentionally accepts a single action object to
    avoid call-site drift between split-argument and object-based forms.
    """

    tx: UdpJsonOut[DensiRemoteAction]

    @staticmethod
    def connect(
        target: tuple[str, int], *, bind: tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpDensiActionOut":
        link = connect_udp_link(target, bind=bind)
        return UdpDensiActionOut(tx=UdpJsonOut(link=link, encode=_encode_action))

    def publish_action(self, action: DensiRemoteAction) -> None:
        """Publish one remote densi action."""

        self.tx.send(action)


def _decode_action(payload: dict[str, object]) -> DensiRemoteAction:
    value = payload.get("value")
    return DensiRemoteAction(
        action=str(payload.get("action", "") or ""),
        value=(bool(value) if value is not None else None),
    )


def _encode_action(action: DensiRemoteAction) -> dict[str, object]:
    payload: dict[str, object] = {"type": "densi_remote_action", "action": str(action.action)}
    if action.value is not None:
        payload["value"] = bool(action.value)
    return payload
