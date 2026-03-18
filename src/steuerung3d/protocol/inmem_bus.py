from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, cast

from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import TelemetrySnapshot


def _new_intent_queue() -> Deque[Intent]:
    return cast(Deque[Intent], deque())


def _new_telemetry_queue() -> Deque[TelemetrySnapshot]:
    return cast(Deque[TelemetrySnapshot], deque())


@dataclass
class InMemBus:
    _intent_q: Deque[Intent] = field(default_factory=_new_intent_queue)
    _telemetry_q: Deque[TelemetrySnapshot] = field(default_factory=_new_telemetry_queue)

    # --- intents (client -> core) ---
    def publish_intent(self, intent: Intent) -> None:
        self._intent_q.append(intent)

    def drain_intents(self, limit: int = 1000) -> List[Intent]:
        out: List[Intent] = []
        n = 0
        while self._intent_q and n < limit:
            out.append(self._intent_q.popleft())
            n += 1
        return out

    # --- telemetry (core -> client) ---
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        self._telemetry_q.append(snap)

    def drain_telemetry(self, limit: int = 1000) -> List[TelemetrySnapshot]:
        out: List[TelemetrySnapshot] = []
        n = 0
        while self._telemetry_q and n < limit:
            out.append(self._telemetry_q.popleft())
            n += 1
        return out
