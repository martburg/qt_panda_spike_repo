from __future__ import annotations

from dataclasses import dataclass
from typing import List

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot

from ..engines.densi.engine_types import DenSiTickResult
from ..engines.densi.viewmodel import DensiViewModel


@dataclass(frozen=True)
class DensiRuntimeResult:
    frames: List[CommandFrame]
    tick_result: DenSiTickResult
    snap: TelemetrySnapshot
    view_model: DensiViewModel
    last_cmd: CommandFrame | None
    last_cmd_ns: int | None
    seen_first_cmd: bool
    cmd_rx_count: int
