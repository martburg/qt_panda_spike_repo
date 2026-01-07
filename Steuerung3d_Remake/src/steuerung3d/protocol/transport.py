from __future__ import annotations

from dataclasses import dataclass, field
from queue import Queue, Empty
from typing import List, Protocol, runtime_checkable

from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import TelemetrySnapshot


@runtime_checkable
class CommandChannel(Protocol):
    def publish_intent(self, intent: Intent) -> None: ...
    def drain_intents(self, limit: int = 1000) -> List[Intent]: ...


@runtime_checkable
class TelemetryChannel(Protocol):
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None: ...
    def drain_telemetry(self, limit: int = 1000) -> List[TelemetrySnapshot]: ...


class Transport(CommandChannel, TelemetryChannel, Protocol):
    """Combined channel interface."""


@dataclass
class InMemTransport:
    """
    Thread-safe in-memory transport.
    Suitable for:
      - unit/integration tests
      - single-process dev stack (core thread + client thread)

    Later we add UDP/ZMQ/WebSocket transports implementing the same interface.
    """
    _intent_q: Queue[Intent] = field(default_factory=Queue)
    _telemetry_q: Queue[TelemetrySnapshot] = field(default_factory=Queue)

    # --- intents ---
    def publish_intent(self, intent: Intent) -> None:
        self._intent_q.put(intent)

    def drain_intents(self, limit: int = 1000) -> List[Intent]:
        out: List[Intent] = []
        for _ in range(limit):
            try:
                out.append(self._intent_q.get_nowait())
            except Empty:
                break
        return out

    # --- telemetry ---
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        self._telemetry_q.put(snap)

    def drain_telemetry(self, limit: int = 1000) -> List[TelemetrySnapshot]:
        out: List[TelemetrySnapshot] = []
        for _ in range(limit):
            try:
                out.append(self._telemetry_q.get_nowait())
            except Empty:
                break
        return out
