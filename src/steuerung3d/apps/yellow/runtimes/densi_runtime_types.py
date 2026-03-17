from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
from typing import Any, List, Protocol, runtime_checkable

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat

from ..engines.densi.engine_types import DenSiTickResult
from ..engines.densi.inputs import DensiInputs
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


@runtime_checkable
class DensiRuntimeTickLike(Protocol):
    _ch: ChangeTracker
    _log: Logger


@runtime_checkable
class DensiRuntimeUiActionsLike(Protocol):
    engine: Any
    _log: Logger
    _force_refresh_checkboxes: bool


@runtime_checkable
class DensiRuntimeDebugLike(Protocol):
    engine: Any
    _axis_ids: list[str]
    _hb: Heartbeat
    _log: Logger
    _lt_last_telem_log_s: float
    _lt_last_cmd_log_s: float
    _lt_last_echo_by_axis: dict[str, int | None]
    _last_cmd_ns: int | None


@runtime_checkable
class DensiRuntimeStatusLike(Protocol):
    engine: Any
    _axis_ids: list[str]
    _stale_after_ms: int
    _seen_first_cmd: bool
    _last_cmd_ns: int | None
    _last_estop: bool
    _last_fault: bool
    _last_mode: str
    _last_cmd: CommandFrame | None
    _status: Any
    _dbg_rl: Any
    _hb: Heartbeat
    _ch: ChangeTracker
    _log: Logger


@runtime_checkable
class DensiRuntimeViewModelLike(Protocol):
    engine: Any
    _axis_ids: list[str]
    _force_refresh_checkboxes: bool


@runtime_checkable
class DensiRuntimeInputLike(Protocol):
    command_in: Any
    action_in: Any
    _log: Logger

    def _apply_ui_actions(self, inputs: DensiInputs) -> None: ...
