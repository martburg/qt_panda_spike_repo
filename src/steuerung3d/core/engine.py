from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.intents import Intent
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.core.state_machine import enforce_mode_actions
from steuerung3d.core.rig_logic import enforce_rig_invariants

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.executor import build_command_frame

StepHook = Callable[[MachineState, float], None]
IntentDrainHook = Callable[[], Sequence[Intent]]
IntentHandlerHook = Callable[[MachineState, Intent], None]
SnapshotHook = Callable[[TelemetrySnapshot], None]
DeviceStepHook = Callable[[MachineState, CommandFrame, float], None]
CommandFrameHook = Callable[[CommandFrame], None]


@dataclass
class CoreEngine:
    timebase: Timebase
    state: MachineState

    # v0.1 hooks
    drain_intents: Optional[IntentDrainHook] = None
    handle_intent: Optional[IntentHandlerHook] = None
    device_step: Optional[DeviceStepHook] = None
    on_step: Optional[StepHook] = None
    on_snapshot: Optional[SnapshotHook] = None
    on_command_frame: Optional[CommandFrameHook] = None

    def step_once(self) -> None:
        dt = self.timebase.dt_s

        # 1) consume intents (client/UI/joystick/program -> core)
        if self.drain_intents is not None and self.handle_intent is not None:
            for intent in self.drain_intents():
                self.handle_intent(self.state, intent)

        # 2) per-tick invariants (rig workflow + mode/safety clamp commands)
        enforce_rig_invariants(self.state)
        enforce_mode_actions(self.state)

        # 3) deterministic tick time forward
        self.state.tick += 1
        self.state.t_s = self.state.tick * dt

        # 4) build command frame and step device (SIM or real adapter)
        cmd_frame = build_command_frame(self.state)

        if self.on_command_frame is not None:
            self.on_command_frame(cmd_frame)

        if self.device_step is not None:
            self.device_step(self.state, cmd_frame, dt)
        elif self.on_step is not None:
            # legacy hook fallback
            self.on_step(self.state, dt)

        # ---- observed device param commit timeout ----
        # If we sent a ParamWrite, we wait for telemetry to confirm the device
        # is actually using those values. If that never happens, surface a
        # timeout (treated as rejection) to HiP via telemetry.
        if hasattr(self.state, "update_param_commit_timeout"):
            max_age_ticks = max(5, int(1.5 / dt)) if dt > 0 else 50
            self.state.update_param_commit_timeout(max_age_ticks=max_age_ticks)

        # ---- NEW: clear one-shot requests after sending once ----
        self.state.estop_reset_req = False
        # parameter ops are also one-shot (they can be re-issued by the UI if needed)
        self.state.pending_param_ops.clear()

        # 5) emit telemetry snapshot
        if self.on_snapshot is not None:
            self.on_snapshot(TelemetrySnapshot.from_state(self.state))

        # one-shot transactional acks (HIP<->Core)
        self.state.core_acks.clear()

    def run_for_ticks(self, n: int) -> None:
        if n < 0:
            raise ValueError("n must be >= 0")
        for _ in range(n):
            self.step_once()
