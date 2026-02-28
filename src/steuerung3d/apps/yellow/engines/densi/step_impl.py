"""DenSi engine tick implementation (extracted).

No semantic changes intended; this is a mechanical extraction from `engine.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import time
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for type checking; avoids runtime import cycles.
    from .engine import DenSiEngine

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.estop_bits import ESTOP_SPECS

from ...domain.estop_facts import (
    decode_estop_word,
    encode_estop_word,
    estop_cause_keys,
    estop_ok_keys,
)

from .types import EStopState, L0Top, L0Sub
from .cut_markers import clear_cut_markers as _clear_cut_markers
from .cut_markers import maybe_latch_cut_markers as _maybe_latch_cut_markers
from .drive_status import update_drive_status_words
from .estop_fsm import (
    apply_estop_state_machine,
    compute_estop_edge_and_update_state as _compute_estop_edge_and_update_state,
    derive_estop_inputs as _derive_estop_inputs,
    sync_reset_able_bit as _sync_reset_able_bit,
)
from .resync import handle_resync_cmd as _handle_resync_cmd
from .param_ops import apply_densi_param_ops
from .motion_clamp import apply_estop_clamp_to_state, compute_moving_guard
from .plc_anton_vel_cmd import step_plc_anton_vel_cmd
from .setpoint_semantics import normalize_cmd_for_plant



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

def step(*, engine: "DenSiEngine", frames: list[CommandFrame], now_ns: int) -> DenSiTickResult:
    """Run one DenSi engine tick."""
    self = engine

    cmd_rx_count = self.rx_command_frames(frames, now_ns=int(now_ns))
    cmd = self.ensure_last_cmd()

    self.update_l0_connection_state(int(now_ns))

    _estop_word0, reset_able, ready_for_sollvel = self.derive_estop_inputs()
    moving = self.compute_moving_guard()

    self.handle_estop_reset_cmd(reset_able)
    self.handle_resync_cmd()

    applied = self.apply_param_ops(ready_for_sollvel=ready_for_sollvel, moving=moving)

    estop_word, bits, reset_able_changed = self.apply_safety_and_refresh_estop()
    estop_edge = self.compute_estop_edge_and_update_state(estop_word)

    self.step_plant_with_clamp()
    self.maybe_latch_cut_markers(estop_edge)
    self.apply_estop_clamp_to_state()
    self.advance_tick()

    # phase 7 (non-Qt semantics):
    motion_ready = bool(
        self.l0_top == L0Top.CONNECTED
        and bool(getattr(self, "drive_ready", False))
        and (not bool(getattr(self.state, "estop", False)))
    )

    # lifetick + status words
    self.step_lifetick()
    update_drive_status_words(
        state=self.state,
        inj_estop_word=int(self.inj_estop_word),
        drive_ready=bool(self.drive_ready),
    )

    return DenSiTickResult(
        cmd_rx_count=cmd_rx_count,
        last_cmd=cmd,
        last_cmd_ns=self.last_cmd_ns,
        l0_top=self.l0_top,
        l0_sub=self.l0_sub,
        reset_able=bool(reset_able),
        ready_for_sollvel=bool(ready_for_sollvel),
        moving=bool(moving),
        motion_ready=bool(motion_ready),
        estop_word=int(estop_word),
        estop_bits=dict(bits),
        estop_edge=bool(estop_edge),
        applied_param_values=dict(applied),
        reset_able_changed=bool(reset_able_changed),
    )
