from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.intents import Intent
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.core.state_machine import enforce_mode_actions

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.executor import drive_legacy_axis_fsms, build_command_frame

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

        # 2) per-tick invariants (mode/safety clamp commands)
        enforce_mode_actions(self.state)

        # 3) deterministic tick time forward
        self.state.tick += 1
        self.state.t_s = self.state.tick * dt

        # 4) drive legacy per-axis FSMs into state.axis_cmd (enable/vel) before building the frame
        drive_legacy_axis_fsms(self.state)

        # 4) build command frame and step device (SIM or real adapter)
        cmd_frame = build_command_frame(self.state)

        if self.on_command_frame is not None:
            self.on_command_frame(cmd_frame)

        if self.device_step is not None:
            self.device_step(self.state, cmd_frame, dt)
        elif self.on_step is not None:
            # legacy hook fallback
            self.on_step(self.state, dt)

        # 5) emit telemetry snapshot
        if self.on_snapshot is not None:
            self.on_snapshot(TelemetrySnapshot.from_state(self.state))
    
    def run_for_ticks(self, n: int) -> None:
        if n < 0:
            raise ValueError("n must be >= 0")
        for _ in range(n):
            self.step_once()
