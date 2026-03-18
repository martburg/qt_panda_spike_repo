from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable, Generic, List, Protocol, Sequence, Tuple, TypeVar, cast

from steuerung3d.adapters.links.udp_link import UdpLink
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.control_context import ControlContext
from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.codec import (
    decode_command_frame,
    decode_control_context,
    decode_intent,
    decode_raw_controls,
    decode_telemetry,
    encode_command_frame,
    encode_control_context,
    encode_intent,
    encode_raw_controls,
    encode_telemetry,
)
from steuerung3d.protocol.raw_controls import RawControls

log = logging.getLogger("udp")

T = TypeVar("T")


def _as_json_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


@dataclass
class UdpJsonIn(Generic[T]):
    link: UdpLink
    decode: Callable[[dict[str, object]], T]

    def drain(self, limit: int = 1000) -> List[T]:
        out: List[T] = []
        for raw in self.link.poll(limit=limit):
            payload = None
            try:
                payload = json.loads(raw.decode("utf-8"))
                payload_dict = _as_json_dict(payload)
                if payload_dict:
                    out.append(self.decode(payload_dict))
            except Exception as e:
                # IMPORTANT: don't swallow decode problems silently (breaks debugging)
                try:
                    payload_dict = _as_json_dict(payload)
                    t = payload_dict.get("type") if payload_dict else None
                except Exception:
                    t = None
                # limit raw size to keep logs readable
                raw_preview = raw[:200]
                log.warning("udp decode failed: type=%r err=%r raw=%r", t, e, raw_preview)
                continue
        return out


@dataclass
class UdpJsonOut(Generic[T]):
    link: UdpLink
    encode: Callable[[T], dict[str, object]]

    def send(self, obj: T) -> None:
        payload = self.encode(obj)
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.link.send(raw)


# Backward-compatible private aliases for existing imports/tests.
_UdpJsonRx = UdpJsonIn
_UdpJsonTx = UdpJsonOut


def close_udp_json_endpoint(endpoint: object) -> None:
    """Close a shared UDP JSON endpoint if it exposes a link-backed rx/tx."""
    try:
        channel = getattr(endpoint, "rx", None) or getattr(endpoint, "tx", None)
        link = getattr(channel, "link", None)
        if link is not None:
            link.close()
    except Exception:
        pass


# ---------- Human input seam ----------
@dataclass
class UdpRawControlsIn:
    rx: UdpJsonIn[RawControls]

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpRawControlsIn":
        link = UdpLink(bind=addr, target=addr)
        return UdpRawControlsIn(rx=UdpJsonIn(link=link, decode=decode_raw_controls))

    def drain_raw_controls(self, limit: int = 1000) -> List[RawControls]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpRawControlsOut:
    tx: UdpJsonOut[RawControls]

    @staticmethod
    def connect(
        target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpRawControlsOut":
        link = UdpLink(bind=bind, target=target)
        return UdpRawControlsOut(tx=UdpJsonOut(link=link, encode=encode_raw_controls))

    def publish_raw_controls(self, rc: RawControls) -> None:
        self.tx.send(rc)


# ---------- Operator seam ----------
@dataclass
class UdpIntentIn:
    rx: UdpJsonIn[Intent]

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpIntentIn":
        link = UdpLink(bind=addr, target=addr)  # target unused for rx
        return UdpIntentIn(rx=UdpJsonIn(link=link, decode=decode_intent))

    def drain_intents(self, limit: int = 1000) -> List[Intent]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpIntentOut:
    tx: UdpJsonOut[Intent]

    @staticmethod
    def connect(
        target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpIntentOut":
        link = UdpLink(bind=bind, target=target)
        return UdpIntentOut(tx=UdpJsonOut(link=link, encode=encode_intent))

    def publish_intent(self, intent: Intent) -> None:
        self.tx.send(intent)


@dataclass
class UdpControlContextIn:
    rx: UdpJsonIn[ControlContext]

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpControlContextIn":
        link = UdpLink(bind=addr, target=addr)
        return UdpControlContextIn(rx=UdpJsonIn(link=link, decode=decode_control_context))

    def drain_contexts(self, limit: int = 1000) -> List[ControlContext]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpControlContextOut:
    tx: UdpJsonOut[ControlContext]

    @staticmethod
    def connect(
        target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpControlContextOut":
        link = UdpLink(bind=bind, target=target)
        return UdpControlContextOut(tx=UdpJsonOut(link=link, encode=encode_control_context))

    def publish_control_context(self, ctx: ControlContext) -> None:
        self.tx.send(ctx)


@dataclass
class UdpTelemetryIn:
    rx: UdpJsonIn[TelemetrySnapshot]

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpTelemetryIn":
        link = UdpLink(bind=addr, target=addr)
        return UdpTelemetryIn(rx=UdpJsonIn(link=link, decode=decode_telemetry))

    def drain_telemetry(self, limit: int = 1000) -> List[TelemetrySnapshot]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpTelemetryOut:
    tx: UdpJsonOut[TelemetrySnapshot]

    @staticmethod
    def connect(
        target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpTelemetryOut":
        link = UdpLink(bind=bind, target=target)
        return UdpTelemetryOut(tx=UdpJsonOut(link=link, encode=encode_telemetry))

    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        self.tx.send(snap)


class TelemetryOut(Protocol):
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None: ...  # pragma: no cover


@dataclass
class UdpTelemetryFanout:
    outs: Sequence[TelemetryOut]

    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        for out in list(self.outs or []):
            try:
                out.publish_telemetry(snap)
            except Exception:
                log.debug("udp fanout send failed", exc_info=True)


# ---------- Device seam ----------
@dataclass
class UdpCommandIn:
    rx: UdpJsonIn[CommandFrame]

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpCommandIn":
        link = UdpLink(bind=addr, target=addr)
        return UdpCommandIn(rx=UdpJsonIn(link=link, decode=decode_command_frame))

    def drain_command_frames(self, limit: int = 1000) -> List[CommandFrame]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpCommandOut:
    tx: UdpJsonOut[CommandFrame]

    @staticmethod
    def connect(
        target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpCommandOut":
        link = UdpLink(bind=bind, target=target)
        return UdpCommandOut(tx=UdpJsonOut(link=link, encode=encode_command_frame))

    def publish_command_frame(self, frame: CommandFrame) -> None:
        self.tx.send(frame)
