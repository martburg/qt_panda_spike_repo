from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import snapshot_from_state

from .bindings import YellowBindings
from .ports import CommandIn, TelemetryOut


@dataclass
class DenSiController:
    """Device Endpoint Simulator (Den-Si): Yellow UI in --role cfc.

    Responsibilities:
      - consume CommandFrame from core (CommandIn)
      - step a small simulated plant at its own dt
      - publish device telemetry back (TelemetryOut)

    This is intentionally tiny; faults/diagnostics get added incrementally.
    """

    win: QWidget
    command_in: CommandIn
    telemetry_out: TelemetryOut
    axis_ids: list[str]
    dt_s: float = 0.01

    def __post_init__(self) -> None:
        self.ui = YellowBindings.from_window(self.win)

        self.tb = Timebase(dt_s=self.dt_s)
        self.state = MachineState()
        for a in self.axis_ids:
            self.state.ensure_axis(a)

        self.device = SimDevice(plant=SimAxisPlant())

        self._last_cmd: CommandFrame | None = None

    def start(self) -> None:
        t = QTimer(self.win)
        t.setInterval(int(self.dt_s * 1000))
        t.timeout.connect(self.step_once)
        t.start()
        self._timer = t

    def step_once(self) -> None:
        # Drain command frames, keep latest
        frames = self.command_in.drain_command_frames(limit=100)
        if frames:
            self._last_cmd = frames[-1]

        # If we don't have a command yet, hold disabled setpoints
        if self._last_cmd is None:
            # Build a safe "all disabled" cmd frame
            self._last_cmd = CommandFrame(
                tick=self.state.tick,
                t_s=self.state.t_s,
                estop=self.state.estop,
                fault=self.state.fault,
                mode=self.state.mode,
                axes={},
            )

        # Step the simulated device
        self.device.step(self.state, self._last_cmd, self.tb.dt_s)

        # Advance device tick/time
        self.state.tick += 1
        self.state.t_s += self.tb.dt_s

        # Publish telemetry (measured)
        snap = snapshot_from_state(self.state)
        self.telemetry_out.publish_telemetry(snap)

        # TODO: update diagnostics UI (last cmd tick/seq etc.)
