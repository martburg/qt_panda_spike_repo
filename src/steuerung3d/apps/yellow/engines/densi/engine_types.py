from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.core.command_frame import CommandFrame

from .types import L0Top, L0Sub


@dataclass
class DenSiTickResult:
    """Result of one DenSi engine tick."""

    cmd_rx_count: int
    last_cmd: CommandFrame
    last_cmd_ns: int | None

    l0_top: L0Top
    l0_sub: L0Sub

    reset_able: bool
    ready_for_sollvel: bool
    moving: bool
    motion_ready: bool

    estop_word: int
    estop_bits: dict[str, bool]
    estop_edge: bool

    applied_param_values: dict[str, float]

    # UI nicety: controller can choose whether to refresh estop checkboxes.
    # Legacy behavior refreshed checkboxes only when ResetAble toggled.
    reset_able_changed: bool = False
