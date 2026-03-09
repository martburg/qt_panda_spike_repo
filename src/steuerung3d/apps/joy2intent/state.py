from __future__ import annotations

from dataclasses import dataclass, field

ControlMode = str  # 'setup_manual' | 'sync_live'


@dataclass
class JoyState:
    # local policy state
    mode: ControlMode = "setup_manual"
    selected_winch_idx: int = 0

    # For momentary multi-select (setup_manual): indices that were actively driven last tick.
    # This lets us emit hard-stops for winches that become deselected or when deadman is released.
    prev_active_winch_idxs: set[int] = field(default_factory=set)

    # previous button states for edge detection
    prev_deadman: bool = False
    prev_mode_toggle: bool = False
    prev_winch_next: bool = False
    prev_winch_prev: bool = False
    prev_arm: bool = False
    prev_disarm: bool = False
    prev_clear_fault: bool = False
    prev_smooth_stop: bool = False

    @property
    def deadman_prev(self) -> bool:
        return bool(self.prev_deadman)

    @deadman_prev.setter
    def deadman_prev(self, value: bool) -> None:
        self.prev_deadman = bool(value)

    @property
    def enabled_winch_ids(self) -> set[str]:
        return {str(idx) for idx in self.prev_active_winch_idxs}

    @enabled_winch_ids.setter
    def enabled_winch_ids(self, value: set[str]) -> None:
        self.prev_active_winch_idxs = {int(v) for v in value if str(v).isdigit()}
