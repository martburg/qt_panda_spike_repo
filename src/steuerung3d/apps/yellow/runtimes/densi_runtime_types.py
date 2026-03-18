from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
from typing import Any, List, Protocol, runtime_checkable

from steuerung3d.apps.supervisor.models import DensiRemoteAction
from steuerung3d.apps.yellow.ports import CommandIn
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat, RateLimiter

from ..engines.densi.engine_types import DenSiTickResult
from ..engines.densi.inputs import DensiInputs
from ..engines.densi.viewmodel import DensiViewModel
from .runtime_utils import StatusEmitterLike


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
class DensiRuntimeStatusPayloadLike(Protocol):
    engine: Any
    _axis_ids: list[str]
    _stale_after_ms: int
    _seen_first_cmd: bool
    _last_cmd_ns: int | None
    _last_estop: bool
    _last_fault: bool
    _last_mode: str
    _last_cmd: CommandFrame | None


@runtime_checkable
class DensiRuntimeStatusLike(DensiRuntimeStatusPayloadLike, Protocol):
    _status: StatusEmitterLike | None
    _dbg_rl: RateLimiter | None
    _hb: Heartbeat
    _ch: ChangeTracker
    _log: Logger


@runtime_checkable
class DensiActionInLike(Protocol):
    def drain_actions(self, limit: int = 1000) -> list[DensiRemoteAction]: ...


@runtime_checkable
class DensiRuntimeViewModelLike(Protocol):
    engine: Any
    _axis_ids: list[str]
    _force_refresh_checkboxes: bool


@runtime_checkable
class DensiRuntimeInputLike(Protocol):
    command_in: CommandIn
    action_in: DensiActionInLike | None
    _log: Logger

    def _apply_ui_actions(self, inputs: DensiInputs) -> None: ...
