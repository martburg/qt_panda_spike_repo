from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import monotonic_ns
from typing import Any, Dict, Iterable, Iterator, Optional

from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.codec import encode_intent, encode_telemetry, decode_intent, decode_telemetry
from steuerung3d.protocol.transport import Transport


LOG_SCHEMA = "steuerung3d.log/v1"


@dataclass
class JsonlRecorder:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write_record(self, rec: Dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def record_intent(self, intent: Intent, tick: Optional[int]) -> None:
        self.write_record({
            "schema": LOG_SCHEMA,
            "kind": "intent",
            "wall_ns": monotonic_ns(),
            "tick": tick,
            "payload": encode_intent(intent),
        })

    def record_telemetry(self, snap: TelemetrySnapshot) -> None:
        self.write_record({
            "schema": LOG_SCHEMA,
            "kind": "telemetry",
            "wall_ns": monotonic_ns(),
            "tick": snap.tick,
            "payload": encode_telemetry(snap),
        })


class JsonlReader:
    def __init__(self, path: Path):
        self.path = path

    def iter_records(self) -> Iterator[Dict[str, Any]]:
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("schema") != LOG_SCHEMA:
                    raise ValueError(f"unexpected schema: {rec.get('schema')}")
                yield rec

    def iter_intents(self) -> Iterator[tuple[Optional[int], Intent]]:
        for rec in self.iter_records():
            if rec["kind"] == "intent":
                yield rec.get("tick"), decode_intent(rec["payload"])

    def iter_telemetry(self) -> Iterator[TelemetrySnapshot]:
        for rec in self.iter_records():
            if rec["kind"] == "telemetry":
                yield decode_telemetry(rec["payload"])


@dataclass
class LoggedTransport(Transport):
    """
    Wraps any Transport and logs:
      - intents published by client
      - telemetry published by core

    Intents are stamped with last seen telemetry tick (best-effort, but deterministic
    for our single-process dev stack).
    """
    inner: Transport
    recorder: JsonlRecorder
    last_tick: int = 0

    # --- intents ---
    def publish_intent(self, intent: Intent) -> None:
        self.recorder.record_intent(intent, tick=self.last_tick)
        self.inner.publish_intent(intent)

    def drain_intents(self, limit: int = 1000):
        return self.inner.drain_intents(limit=limit)

    # --- telemetry ---
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        self.last_tick = snap.tick
        self.recorder.record_telemetry(snap)
        self.inner.publish_telemetry(snap)

    def drain_telemetry(self, limit: int = 1000):
        return self.inner.drain_telemetry(limit=limit)
