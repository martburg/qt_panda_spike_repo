from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Generic, List, Tuple, TypeVar

from steuerung3d.adapters.links.udp_link import UdpLink
from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.protocol.codec import (
    encode_intent, decode_intent,
    encode_telemetry, decode_telemetry,
    encode_command_frame, decode_command_frame,
)

T = TypeVar("T")


@dataclass
class _UdpJsonRx(Generic[T]):
    link: UdpLink
    decode: Callable[[dict], T]

    def drain(self, limit: int = 1000) -> List[T]:
        out: List[T] = []
        for raw in self.link.poll(limit=limit):
            try:
                payload = json.loads(raw.decode("utf-8"))
                if isinstance(payload, dict):
                    out.append(self.decode(payload))
            except Exception:
                # keep it robust; later we add stats/logging
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


# ---------- Operator seam ----------
@dataclass
class UdpIntentIn:
    rx: _UdpJsonRx[Intent]

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpIntentIn":
        link = UdpLink(bind=addr, target=addr)  # target unused for rx
        return UdpIntentIn(rx=_UdpJsonRx(link=link, decode=decode_intent))

    def drain_intents(self, limit: int = 1000) -> List[Intent]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpIntentOut:
    tx: _UdpJsonTx[Intent]

    @staticmethod
    def connect(target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)) -> "UdpIntentOut":
        link = UdpLink(bind=bind, target=target)
        return UdpIntentOut(tx=_UdpJsonTx(link=link, encode=encode_intent))

    def publish_intent(self, intent: Intent) -> None:
        self.tx.send(intent)


@dataclass
class UdpTelemetryIn:
    rx: _UdpJsonRx[TelemetrySnapshot]

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpTelemetryIn":
        link = UdpLink(bind=addr, target=addr)
        return UdpTelemetryIn(rx=_UdpJsonRx(link=link, decode=decode_telemetry))

    def drain_telemetry(self, limit: int = 1000) -> List[TelemetrySnapshot]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpTelemetryOut:
    tx: _UdpJsonTx[TelemetrySnapshot]

    @staticmethod
    def connect(target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)) -> "UdpTelemetryOut":
        link = UdpLink(bind=bind, target=target)
        return UdpTelemetryOut(tx=_UdpJsonTx(link=link, encode=encode_telemetry))

    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        self.tx.send(snap)


# ---------- Device seam ----------
@dataclass
class UdpCommandIn:
    rx: _UdpJsonRx[CommandFrame]

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpCommandIn":
        link = UdpLink(bind=addr, target=addr)
        return UdpCommandIn(rx=_UdpJsonRx(link=link, decode=decode_command_frame))

    def drain_command_frames(self, limit: int = 1000) -> List[CommandFrame]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpCommandOut:
    tx: _UdpJsonTx[CommandFrame]

    @staticmethod
    def connect(target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)) -> "UdpCommandOut":
        link = UdpLink(bind=bind, target=target)
        return UdpCommandOut(tx=_UdpJsonTx(link=link, encode=encode_command_frame))

    def publish_command_frame(self, frame: CommandFrame) -> None:
        self.tx.send(frame)
