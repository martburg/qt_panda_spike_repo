from __future__ import annotations

from dataclasses import dataclass, field
from queue import Queue, Empty
from typing import List, Protocol, runtime_checkable

from steuerung3d.core.intents import Intent
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.raw_controls import RawControls


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


# ------------------------------
# Transport v2 (multi-stream)
#
# We keep the original v1 Transport (intents + telemetry) stable for existing
# code and tests. New code should prefer TransportV2.
# ------------------------------


@runtime_checkable
class RawControlsChannel(Protocol):
    def publish_raw_controls(self, rc: RawControls) -> None: ...
    def drain_raw_controls(self, limit: int = 1000) -> List[RawControls]: ...


@runtime_checkable
class CommandFrameChannel(Protocol):
    def publish_command_frame(self, frame: CommandFrame) -> None: ...
    def drain_command_frames(self, limit: int = 1000) -> List[CommandFrame]: ...


class TransportV2(CommandChannel, TelemetryChannel, RawControlsChannel, CommandFrameChannel, Protocol):
    """Combined channel interface for all runtime streams."""


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


@dataclass
class InMemTransportV2:
    """Thread-safe in-memory transport for the full v2 stream set.

    Streams:
      - raw_controls (inputd -> joy2intent)
      - intents (client -> core)
      - command_frames (core -> device adapters)
      - telemetry (core/device -> UI)
    """
    _raw_q: Queue[RawControls] = field(default_factory=Queue)
    _intent_q: Queue[Intent] = field(default_factory=Queue)
    _cmd_q: Queue[CommandFrame] = field(default_factory=Queue)
    _telemetry_q: Queue[TelemetrySnapshot] = field(default_factory=Queue)

    # --- raw controls ---
    def publish_raw_controls(self, rc: RawControls) -> None:
        self._raw_q.put(rc)

    def drain_raw_controls(self, limit: int = 1000) -> List[RawControls]:
        out: List[RawControls] = []
        for _ in range(limit):
            try:
                out.append(self._raw_q.get_nowait())
            except Empty:
                break
        return out

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

    # --- command frames ---
    def publish_command_frame(self, frame: CommandFrame) -> None:
        self._cmd_q.put(frame)

    def drain_command_frames(self, limit: int = 1000) -> List[CommandFrame]:
        out: List[CommandFrame] = []
        for _ in range(limit):
            try:
                out.append(self._cmd_q.get_nowait())
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
