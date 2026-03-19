from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .models import SupervisorProfile

_RESET_LOG_TOKEN: Final[str] = "cmd_estop_reset=True"
_ESTART_LOG_TOKEN: Final[str] = "ESStart pressed"
_CORE_IDLE_TOKEN: Final[str] = "core_mode=IDLE"
_HIP_SMOKE_CONTROL_BASE: Final[int] = 54001


@dataclass(frozen=True)
class SmokeSequenceConfig:
    supervisor_profile_path: Path
    startup_timeout_s: float = 20.0
    ready_grace_s: float = 1.0
    observe_timeout_s: float = 8.0
    settle_s: float = 0.25
    publish_interval_s: float = 0.25
    keep_running: bool = False
    brake_grace_s: float = 2.0
    motion_pos_delta_min: float = 0.2
    motion_vel_move_eps: float = 0.05
    motion_vel_zero_eps: float = 0.05
    motion_release_settle_s: float = 0.5
    hip_param_axis_id: str = ""
    hip_param_restore_after_write: bool = True


@dataclass(frozen=True)
class SmokeSequenceResult:
    session_dir: Path
    selected_axis_ids: tuple[str, ...]
    observed_reset_log_names: tuple[str, ...]
    observed_estart_log_names: tuple[str, ...] = ()
    observed_system_time_axis_ids: tuple[str, ...] = ()
    system_time_first_by_axis: Mapping[str, str] | None = None
    system_time_last_by_axis: Mapping[str, str] | None = None
    system_time_first_tick_by_axis: Mapping[str, int] | None = None
    system_time_last_tick_by_axis: Mapping[str, int] | None = None
    reset_publish_count: int = 0
    estart_publish_count: int = 0
    resync_publish_count: int = 0
    chk_taster_publish_count: int = 0
    observed_chk_ready_axis_ids: tuple[str, ...] = ()
    chk_phase_before_by_axis: Mapping[str, str] | None = None
    chk_phase_first_active_by_axis: Mapping[str, str] | None = None
    chk_phase_final_by_axis: Mapping[str, str] | None = None
    chk_armed_axis_ids: tuple[str, ...] = ()
    chk_ready_axis_ids: tuple[str, ...] = ()
    motion_command_publish_count: int = 0
    observed_motion_axis_ids: tuple[str, ...] = ()
    observed_stop_axis_ids: tuple[str, ...] = ()
    motion_start_pos_by_axis: Mapping[str, float] | None = None
    motion_end_pos_by_axis: Mapping[str, float] | None = None
    motion_delta_by_axis: Mapping[str, float] | None = None
    motion_max_abs_vel_by_axis: Mapping[str, float] | None = None
    motion_final_abs_vel_by_axis: Mapping[str, float] | None = None


class SmokeSequenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class HiPParamSmokeResult:
    session_dir: Path
    axis_id: str
    hip_id: str
    observed_reset_log_names: tuple[str, ...]
    observed_estart_log_names: tuple[str, ...]
    observed_system_time_axis_ids: tuple[str, ...]
    reset_publish_count: int
    estart_publish_count: int
    resync_publish_count: int
    open_hip_command_count: int
    param_command_count: int
    param_restore_command_count: int
    selected_axis_ids: tuple[str, ...] = ()
    owner_before: str = ""
    owner_after_open: str = ""
    parameter_name: str = ""
    parameter_group: str = ""
    original_value: float = 0.0
    edited_value: float = 0.0
    observed_value_after_write: float = 0.0
    observed_commit_status_after_write: str = ""
    observed_value_after_restore: float = 0.0
    observed_commit_status_after_restore: str = ""
    restored: bool = False


@dataclass(frozen=True)
class HiPOpenObservation:
    axis_id: str
    owner_before: str
    owner_after: str


@dataclass(frozen=True)
class HiPParamObservation:
    observed_value: float
    commit_status: str


@dataclass(frozen=True)
class SystemTimeProgressObservation:
    observed_axis_ids: tuple[str, ...]
    first_by_axis: Mapping[str, str]
    last_by_axis: Mapping[str, str]
    first_tick_by_axis: Mapping[str, int]
    last_tick_by_axis: Mapping[str, int]


@dataclass(frozen=True)
class ChkEsTasterObservation:
    observed_axis_ids: tuple[str, ...]
    before_by_axis: Mapping[str, str]
    first_active_by_axis: Mapping[str, str]
    final_by_axis: Mapping[str, str]
    armed_axis_ids: tuple[str, ...]
    ready_axis_ids: tuple[str, ...]


@dataclass(frozen=True)
class MotionObservation:
    moving_axis_ids: tuple[str, ...]
    stopped_axis_ids: tuple[str, ...]
    start_pos_by_axis: Mapping[str, float]
    end_pos_by_axis: Mapping[str, float]
    delta_by_axis: Mapping[str, float]
    max_abs_vel_by_axis: Mapping[str, float]
    final_abs_vel_by_axis: Mapping[str, float]


@dataclass(frozen=True)
class IdleSyncedBootstrap:
    launched: _LaunchedSupervisor
    selected_axis_ids: tuple[str, ...]
    observed_reset: set[str]
    observed_estart: set[str]
    system_time_progress: SystemTimeProgressObservation
    reset_publish_count: int
    estart_publish_count: int
    resync_publish_count: int


@dataclass
class _LaunchedSupervisor:
    process: subprocess.Popen[str]
    session_dir: Path
    profile: SupervisorProfile
    stack_profile_path: Path
    supervisor_action_in_addr: str
    inputd_sim_control_in_addr: str
    hip_smoke_control_base: int


@dataclass(frozen=True)
class SelectedActionTarget:
    axis_id: str
    unit_id: str
    densi_process_name: str
    action_out_addr: str
