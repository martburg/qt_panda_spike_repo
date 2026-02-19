from __future__ import annotations

from typing import List, Protocol, runtime_checkable

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import TelemetrySnapshot


@runtime_checkable
class IntentOut(Protocol):
    def publish_intent(self, intent: Intent) -> None: ...


@runtime_checkable
class TelemetryIn(Protocol):
    def drain_telemetry(self, limit: int = 1000) -> List[TelemetrySnapshot]: ...


@runtime_checkable
class CommandIn(Protocol):
    def drain_command_frames(self, limit: int = 1000) -> List[CommandFrame]: ...


@runtime_checkable
class TelemetryOut(Protocol):
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None: ...
