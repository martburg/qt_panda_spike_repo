from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import monotonic_ns
from typing import Any, Dict, Iterable, Iterator, List, Optional

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.codec import (
    decode_command_frame,
    decode_intent,
    decode_raw_controls,
    decode_telemetry,
    encode_command_frame,
    encode_intent,
    encode_raw_controls,
    encode_telemetry,
)
from steuerung3d.protocol.raw_controls import RawControls
from steuerung3d.protocol.transport import Transport, TransportV2

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

    def record_raw_controls(self, rc: RawControls, tick: Optional[int]) -> None:
        self.write_record({
            "schema": LOG_SCHEMA,
            "kind": "raw_controls",
            "wall_ns": monotonic_ns(),
            "tick": tick,
            "payload": encode_raw_controls(rc),
        })

    def record_command_frame(self, frame: CommandFrame) -> None:
        self.write_record({
            "schema": LOG_SCHEMA,
            "kind": "command_frame",
            "wall_ns": monotonic_ns(),
            "tick": frame.tick,
            "payload": encode_command_frame(frame),
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

    def iter_raw_controls(self) -> Iterator[tuple[Optional[int], RawControls]]:
        for rec in self.iter_records():
            if rec.get("kind") == "raw_controls":
                yield rec.get("tick"), decode_raw_controls(rec["payload"])

    def iter_command_frames(self) -> Iterator[CommandFrame]:
        for rec in self.iter_records():
            if rec.get("kind") == "command_frame":
                yield decode_command_frame(rec["payload"])


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


@dataclass
class LoggedTransportV2(TransportV2):
    """Logged wrapper for TransportV2.

    This extends JSONL logging to additional streams:
      - raw_controls published by input devices
      - command_frames published by core
    """

    inner: TransportV2
    recorder: JsonlRecorder
    last_tick: int = 0

    # --- raw controls ---
    def publish_raw_controls(self, rc: RawControls) -> None:
        self.recorder.record_raw_controls(rc, tick=self.last_tick)
        self.inner.publish_raw_controls(rc)

    def drain_raw_controls(self, limit: int = 1000) -> List[RawControls]:
        return self.inner.drain_raw_controls(limit=limit)

    # --- intents ---
    def publish_intent(self, intent: Intent) -> None:
        self.recorder.record_intent(intent, tick=self.last_tick)
        self.inner.publish_intent(intent)

    def drain_intents(self, limit: int = 1000) -> List[Intent]:
        return self.inner.drain_intents(limit=limit)

    # --- command frames ---
    def publish_command_frame(self, frame: CommandFrame) -> None:
        self.recorder.record_command_frame(frame)
        self.inner.publish_command_frame(frame)

    def drain_command_frames(self, limit: int = 1000) -> List[CommandFrame]:
        return self.inner.drain_command_frames(limit=limit)

    # --- telemetry ---
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        self.last_tick = snap.tick
        self.recorder.record_telemetry(snap)
        self.inner.publish_telemetry(snap)

    def drain_telemetry(self, limit: int = 1000) -> List[TelemetrySnapshot]:
        return self.inner.drain_telemetry(limit=limit)
