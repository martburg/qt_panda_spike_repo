"""Hip engine data types (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry import TelemetrySnapshot

from ...domain.param_txn import RetryEvent

if TYPE_CHECKING:  # pragma: no cover
    from .viewmodel import HipCutMarkersState, HipDriveStatusState, HipReadoutsState, HipViewModel


@dataclass(frozen=True)
class HipAttachInputs:
    attached: bool
    modal_locked: bool
    last_mode: str
    last_estate: str


@dataclass(frozen=True)
class HipAttachState:
    attached: bool
    tabs_enabled: bool | None
    setup_enabled: bool
    main_amp_reset_enabled: bool
    guider_amp_reset_enabled: bool
    resync_enabled: bool
    estop_reset_enabled: bool | None


@dataclass(frozen=True)
class HipBannerInputs:
    estop_word: int
    within_brake_grace: bool


@dataclass(frozen=True)
class HipAttachCombo:
    items: list[str]
    current: str
    enabled: bool
    fixed_axis_applied: bool


@dataclass(frozen=True)
class HipParamAction:
    kind: str  # edit|write|cancel
    group: str


@dataclass(frozen=True)
class HipUiInputs:
    axis_selected: str
    axis_selection_changed: bool
    estop_reset_clicked: bool
    resync_clicked: bool
    param_actions: list[HipParamAction]
    param_values: dict[str, dict[str, float]]
    main_reset_clicked: bool = False
    guider_reset_clicked: bool = False


@dataclass(frozen=True)
class HipParamButtons:
    edit_enabled: bool
    write_enabled: bool
    cancel_enabled: bool


@dataclass(frozen=True)
class HipParamGroup:
    fields_enabled: bool
    buttons: HipParamButtons


@dataclass(frozen=True)
class HipParamUiState:
    modal_lock_active: bool
    modal_lock_group: str
    groups: dict[str, HipParamGroup]


@dataclass(frozen=True)
class HipParamCommitDialog:
    level: str  # "info" | "warning"
    title: str
    message: str


@dataclass
class HipState:
    prev_device_tick: int | None = None
    last_lifetick_echo_sent: dict[str, int] = field(default_factory=dict)
    selected_axis: str = ""
    fixed_axis_applied: bool = False
    last_ui_axis_selected: str = ""
    prev_estop_profile: str = ""
    pending_commit_req_id: str = ""
    pending_commit_group: str = ""
    pending_commit_values: dict[str, float] = field(default_factory=dict)
    commit_dialog_shown_for: set[str] = field(default_factory=set)
    joy: JoyState = field(default_factory=JoyState)
    last_claim_attempt_ns_by_axis: dict[str, int] = field(default_factory=dict)
    last_sent_speed_by_axis: dict[str, float] = field(default_factory=dict)
    last_sent_enable_by_axis: dict[str, bool] = field(default_factory=dict)
    joy_jog_active: bool = False
    joy_jog_axis: str = ""


@dataclass(frozen=True)
class HipStepInputs:
    snap: TelemetrySnapshot
    hip_id: str
    last_rx_ns: int | None
    now_ns: int
    stale_after_ms: int
    fixed_axis: str
    lock_axis_combo: bool
    last_mode: str
    last_estate: str
    ui: HipUiInputs
    core_acks: list[str]
    joy: JoyState


@dataclass(frozen=True)
class HipStepResult:
    view_model: "HipViewModel | None"
    legacy_view_model: "HipViewModel | None"
    presentation: "HipPresentationData"
    intents: list[object]
    resync_ignored: bool
    resync_block_reason: str
    txn_events: list[RetryEvent] = field(default_factory=list)


@dataclass(frozen=True)
class HipPresentationData:
    tick_text: str
    age_ms: int | None
    stale: bool
    lifetick_age: int | None
    online_state: str | None
    estop: bool
    fault: bool
    drive_status_summary: str
    drive_status: "HipDriveStatusState"
    estop_word: int
    within_banner: bool
    within_brake: bool
    logical: dict[str, bool]
    taster: bool
    attached: bool
    prev_estop_profile: str
    joy_deadman: bool
    joy_select_hip: bool
    joy_soll_speed: float
    readouts: "HipReadoutsState | None"
    cut_markers: "HipCutMarkersState | None"
    attach_state: HipAttachState | None
    attach_combo: HipAttachCombo | None
    param_ui: HipParamUiState | None
    param_values: dict[str, float]
    param_freeze_group: str
    limit_values: dict[str, float]
    param_writeback_group: str
    param_writeback_values: dict[str, float]
    param_writeback_message: str
    param_commit_dialog: HipParamCommitDialog | None
