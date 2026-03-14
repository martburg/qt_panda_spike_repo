from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from steuerung3d.adapters.links.udp_link import UdpLink

from .models import DensiRemoteAction

T = TypeVar("T")


@dataclass
class _UdpJsonRx(Generic[T]):
    link: UdpLink
    decode: Callable[[dict], T]

    def drain(self, limit: int = 1000) -> list[T]:
        out: list[T] = []
        for raw in self.link.poll(limit=limit):
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict):
                try:
                    out.append(self.decode(payload))
                except Exception:
                    continue
        return out


@dataclass
class _UdpJsonTx(Generic[T]):
    link: UdpLink
    encode: Callable[[T], dict]

    def send(self, obj: T) -> None:
        payload = self.encode(obj)
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.link.send(raw)


@dataclass(frozen=True)
class UdpDensiActionIn:
    rx: _UdpJsonRx[DensiRemoteAction]

    @staticmethod
    def bind(addr: tuple[str, int]) -> "UdpDensiActionIn":
        link = UdpLink(bind=addr, target=addr)
        return UdpDensiActionIn(rx=_UdpJsonRx(link=link, decode=_decode_action))

    def drain_actions(self, limit: int = 1000) -> list[DensiRemoteAction]:
        return self.rx.drain(limit=limit)


@dataclass(frozen=True)
class UdpDensiActionOut:
    tx: _UdpJsonTx[DensiRemoteAction]

    @staticmethod
    def connect(
        target: tuple[str, int], *, bind: tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpDensiActionOut":
        link = UdpLink(bind=bind, target=target)
        return UdpDensiActionOut(tx=_UdpJsonTx(link=link, encode=_encode_action))

    def publish_action(self, action: DensiRemoteAction) -> None:
        self.tx.send(action)


def _decode_action(payload: dict) -> DensiRemoteAction:
    return DensiRemoteAction(
        action=str(payload.get("action", "") or ""), value=payload.get("value")
    )


def _encode_action(action: DensiRemoteAction) -> dict:
    payload = {"type": "densi_remote_action", "action": str(action.action)}
    if action.value is not None:
        payload["value"] = bool(action.value)
    return payload
