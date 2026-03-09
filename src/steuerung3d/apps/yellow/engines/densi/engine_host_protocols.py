from __future__ import annotations

from typing import Callable, Protocol

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState

from .types import EStopState, L0Sub, L0Top


class DenSiEngineHost(Protocol):
    axis_ids: list[str]
    tb: Timebase
    state: MachineState

    disconnect_after_s: float
    seen_first_cmd: bool
    last_cmd: CommandFrame | None
    last_cmd_ns: int | None
    l0_top: L0Top
    l0_sub: L0Sub

    normalize_pos_chain: Callable[[dict[str, float]], dict[str, float]] | None
    normalize_guider_range: Callable[[dict[str, float]], dict[str, float]] | None
    enforce_pos_chain: Callable[[dict[str, float]], dict[str, float]] | None
    enforce_guider_minmax: Callable[[dict[str, float]], dict[str, float]] | None
    drive_ready: bool
    lifetick_stale_after_ticks_active: int
    lifetick_stale_after_ticks_idle: int

    inj_bits: dict[str, bool] | None
    inj_estop_word: int
    taster_prev: bool
    taster_rise_t_s: float | None
    taster_prev_disp: bool
    taster_pressed_s: float | None
    estate: EStopState
    brake_switch_s: float
    brake_handoff_grace_s: float
    es_start_armed: bool
    estop_latched: bool
    safety_ok: bool
    brake_override_b1: bool
    brake_override_b2: bool

    cut_valid: bool
    cut_pos_m: float
    cut_vel_mps: float
    cut_time_s: float
    systemtime_tok: str
    prev_estop_state: bool
    cut_follow_live: bool
    prev_cause_active: bool
    cause_active: bool
    cause_edge: bool
    stop_valid: bool
    stop_pos_m: float
    stop_time_s: float
    posdiff_stop_m: float

    def _now_token(self) -> str: ...
    def within_brake_grace_disp(self) -> bool: ...
    def _update_display_grace_tracking(self) -> None: ...
    def clear_cut_markers(self, *, reset_prev: bool = False) -> None: ...
    def arm_cut_follow_live(self) -> None: ...
    def ensure_last_cmd(self) -> CommandFrame: ...
    def apply_estop_state_machine(self) -> None: ...
    def sync_reset_able_bit(self) -> bool: ...
