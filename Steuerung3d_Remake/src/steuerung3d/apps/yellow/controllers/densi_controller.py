from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QCheckBox

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot

from .bindings import YellowBindings
from .ports import CommandIn, TelemetryOut

import logging

log = logging.getLogger("den_si")

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

        self._inj_estop = False  # injected diagnostic estop bits (device-side)

        self._estop_latched = False
        self._safety_ok = True   # sim placeholder (later comes from safety SPS / another channel)


        # Wire diagnostic E-Stop buttons (device-side simulation inputs)
        if self.ui.btn_estop_all_set is not None:
            self.ui.btn_estop_all_set.clicked.connect(lambda: self._set_inj_estop(True))
        if self.ui.btn_estop_all_clear is not None:
            self.ui.btn_estop_all_clear.clicked.connect(lambda: self._set_inj_estop(False))

    def _set_inj_estop(self, value: bool) -> None:
        try:
            self._inj_estop = bool(value)
            log.info("inject estop=%s", self._inj_estop)

            # update readback checkboxes (optional but nice)
            for name in ("chkEStopMaster", "chkEStopGuider", "chkEStopNetwork", "chkEStop1", "chkEStop2"):
                w = self.win.findChild(QCheckBox, name)
                if w is not None:
                    w.setChecked(self._inj_estop)
        except Exception:
            log.exception("inject estop handler failed")

    def start(self) -> None:
        t = QTimer(self.win)
        t.setInterval(int(self.dt_s * 1000))
        t.timeout.connect(self.step_once)
        t.start()
        self._timer = t

    def step_once(self) -> None:
        frames = self.command_in.drain_command_frames(limit=100)
        if frames:
            self._last_cmd = frames[-1]
            log.debug("rx cmd: tick=%s estop=%s fault=%s mode=%s", self._last_cmd.tick, self._last_cmd.estop, self._last_cmd.fault, self._last_cmd.mode)


        if self._last_cmd is None:
            self._last_cmd = CommandFrame(
                tick=self.state.tick,
                t_s=self.state.t_s,
                estop=False,
                fault=False,
                mode=self.state.mode,
                axes={},
                estop_reset=self.state.estop_reset_req,
            )

        # 1) Trip condition (device authoritative)
        trip = bool(self._inj_estop) or (not self._safety_ok)

        # 2) Latch on trip
        if trip:
            self._estop_latched = True

        # 3) Clear latch only if reset requested AND safety is OK AND no trip right now
        if getattr(self._last_cmd, "estop_reset", False) and self._safety_ok and not self._inj_estop:
            self._estop_latched = False
            log.info("estop latch cleared (reset request accepted)")

        # 4) Publish authoritative estop state
        self.state.estop = self._estop_latched

        # Step the simulated device
        self.device.step(self.state, self._last_cmd, self.tb.dt_s)

        # Enforce "stop" semantics even if the plant doesn't implement it yet
        if self.state.estop:
            for ax in self.state.axes.values():
                ax.enabled = False
                ax.vel = 0.0

        self.state.tick += 1
        self.state.t_s += self.tb.dt_s

        snap = TelemetrySnapshot.from_state(self.state)
        self.telemetry_out.publish_telemetry(snap)

        # after publishing telemetry
        log.debug("tx telem: tick=%s estop=%s fault=%s", snap.tick, snap.estop, snap.fault)