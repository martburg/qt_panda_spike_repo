from __future__ import annotations

from typing import Any, Protocol, cast

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot


class CommandFrameSink(Protocol):
    def publish_command_frame(self, frame: CommandFrame) -> None: ...


class TelemetrySink(Protocol):
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None: ...


def empty_telemetry_sinks() -> list[TelemetrySink]:
    return []


def make_snapshot(**kwargs: Any) -> TelemetrySnapshot:
    ctor = cast(Any, TelemetrySnapshot)
    return ctor(**kwargs)
