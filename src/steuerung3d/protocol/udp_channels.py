from __future__ import annotations

import json
from dataclasses import dataclass
import logging
from typing import Callable, Generic, List, Tuple, TypeVar

from steuerung3d.adapters.links.udp_link import UdpLink
from steuerung3d.core.intents import Intent
from steuerung3d.protocol.raw_controls import RawControls
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.protocol.codec import (
    encode_intent, decode_intent,
    encode_raw_controls, decode_raw_controls,
    encode_telemetry, decode_telemetry,
    encode_command_frame, decode_command_frame,
)

log = logging.getLogger("udp")

T = TypeVar("T")


@dataclass
class _UdpJsonRx(Generic[T]):
    link: UdpLink
    decode: Callable[[dict], T]

    def drain(self, limit: int = 1000) -> List[T]:
        out: List[T] = []
        for raw in self.link.poll(limit=limit):
            payload = None
            try:
                payload = json.loads(raw.decode("utf-8"))
                if isinstance(payload, dict):
                    out.append(self.decode(payload))
            except Exception as e:
                # IMPORTANT: don't swallow decode problems silently (breaks debugging)
                try:
                    t = payload.get("type") if isinstance(payload, dict) else None
                except Exception:
                    t = None
                # limit raw size to keep logs readable
                raw_preview = raw[:200] if isinstance(raw, (bytes, bytearray)) else b""
                log.warning("udp decode failed: type=%r err=%r raw=%r", t, e, raw_preview)
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


# ---------- Human input seam ----------
@dataclass
class UdpRawControlsIn:
    rx: _UdpJsonRx[RawControls]

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpRawControlsIn":
        link = UdpLink(bind=addr, target=addr)
        return UdpRawControlsIn(rx=_UdpJsonRx(link=link, decode=decode_raw_controls))

    def drain_raw_controls(self, limit: int = 1000) -> List[RawControls]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpRawControlsOut:
    tx: _UdpJsonTx[RawControls]

    @staticmethod
    def connect(target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)) -> "UdpRawControlsOut":
        link = UdpLink(bind=bind, target=target)
        return UdpRawControlsOut(tx=_UdpJsonTx(link=link, encode=encode_raw_controls))

    def publish_raw_controls(self, rc: RawControls) -> None:
        self.tx.send(rc)


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


@dataclass
class UdpTelemetryFanout:
    outs: List[UdpTelemetryOut]

    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        for out in list(self.outs or []):
            try:
                out.publish_telemetry(snap)
            except Exception:
                log.debug("udp fanout send failed", exc_info=True)


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
