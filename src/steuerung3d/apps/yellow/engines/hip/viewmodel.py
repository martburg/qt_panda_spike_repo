"""Hip view-model types (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import HipAttachCombo, HipAttachState, HipParamCommitDialog, HipParamUiState


@dataclass(frozen=True)
class HipBannerState:
    estate: str
    bg: str
    fg: str
    left_text: str
    right_text: str


@dataclass(frozen=True)
class HipHeaderDots:
    online_state: str | None
    ready_state: str | None
    fbt_state: str | None
    brk1_state: str | None
    brk2_state: str | None


@dataclass(frozen=True)
class HipDriveStatusState:
    main_text: str
    slave_text: str


@dataclass(frozen=True)
class HipEstopState:
    dots: dict[str, str | None]
    reset_enabled: bool
    checkbox_states: dict[str, bool]
    active_keys: set[str]
    profile_changed: bool


@dataclass(frozen=True)
class HipReadoutsState:
    pos_text: str
    vel_text: str
    amp_text: str
    temp_text: str
    guider_min_text: str
    guider_max_text: str
    guider_val_text: str
    guider_speed_text: str
    vel_cmd_min: int
    vel_cmd_max: int
    vel_cmd_val: int
    limit_min: int
    limit_max: int
    limit_val: int
    guider_range_min: int
    guider_range_max: int
    guider_range_val: int
    guider_speed_min: int
    guider_speed_max: int
    guider_speed_val: int


@dataclass(frozen=True)
class HipCutMarkersState:
    cut_time_text: str
    cut_pos_text: str
    cut_vel_text: str
    posdiff_text: str


@dataclass(frozen=True)
class HipViewModel:
    tick_text: str
    age_ms: int | None
    stale: bool
    lifetick_age: int | None
    online_state: str | None
    estop: bool
    fault: bool
    drive_status_summary: str
    joy_deadman: bool = False
    joy_select_hip: bool = False
    joy_soll_speed: float = 0.0
    banner: HipBannerState | None = None
    header_dots: HipHeaderDots | None = None
    drive_status: HipDriveStatusState | None = None
    estop_state: HipEstopState | None = None
    readouts: HipReadoutsState | None = None
    cut_markers: HipCutMarkersState | None = None
    attach_state: HipAttachState | None = None
    attach_combo: HipAttachCombo | None = None
    param_ui: HipParamUiState | None = None
    param_values: dict[str, float] = field(default_factory=dict)
    param_freeze_group: str = ""
    limit_values: dict[str, float] = field(default_factory=dict)
    param_writeback_group: str = ""
    param_writeback_values: dict[str, float] = field(default_factory=dict)
    param_writeback_message: str = ""
    param_commit_dialog: HipParamCommitDialog | None = None
