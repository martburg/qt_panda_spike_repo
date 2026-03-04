"""DenSi engine tick implementation (extracted).

No semantic changes intended; this is a mechanical extraction from `engine.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for type checking; avoids runtime import cycles.
    from .engine import DenSiEngine

from steuerung3d.core.command_frame import CommandFrame

from .drive_status import update_drive_status_words
from .engine_types import DenSiTickResult
from .types import L0Top


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

    # If ReSync armed live baseline tracking, update CutPos/CutVel in IDLE.
    self.update_cut_follow_live()

    # Latch cut markers on the transition into E-Stop.
    #
    # Contract: CutPos/CutVel/CutTime must freeze whenever we enter E-Stop.
    # We therefore use the authoritative `estop_edge` computed from the
    # ESTOP state machine rather than any "cause" detector.
    self.maybe_latch_cut_markers(bool(estop_edge))

    # Step the plant: during E-Stop this models a Dcc-limited ramp-down.
    self.step_plant_with_clamp()

    # Once the axis stops (v~=0), latch the coastdown distance.
    self.maybe_latch_stop_metrics()
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
