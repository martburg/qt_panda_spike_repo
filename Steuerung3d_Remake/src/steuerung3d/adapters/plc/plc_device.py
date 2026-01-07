from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from steuerung3d.adapters.links.base import Link
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState

from .plc_codec import PlcCodec


@dataclass
class PlcDevice:
    """
    Device adapter that plugs into CoreEngine.device_step.

    Per tick:
      - TX: send full-state setpoints (idempotent; safe under drop/dup)
      - RX: drain UDP telemetry (latest wins)
      - Apply measured state into MachineState (device authoritative)

    Ownership policy (v0.1 default here):
      - estop/fault: treated as device-reported truth (overwrites state)
      - mode: kept core-owned (we do NOT overwrite MachineState.mode),
              but telemetry snapshots will carry PLC-reported mode string separately
              if you choose to log it.
    """
    link: Link
    codec: PlcCodec
    last_rx_tick: Optional[int] = None

    def step(self, state: MachineState, cmd: CommandFrame, dt: float) -> None:
        # --- TX ---
        self.link.send(self.codec.encode_command_frame(cmd))

        # --- RX (latest wins) ---
        latest = None
        for dat in self.link.poll(limit=100):
            snap = self.codec.try_decode_telemetry(dat)
            if snap is not None:
                latest = snap

        if latest is None:
            return

        self.last_rx_tick = latest.tick

        # Apply device-reported health flags
        state.estop = latest.estop
        state.fault = latest.fault

        # Apply measured axis states
        for axis_id, ax_t in latest.axes.items():
            ax = state.ensure_axis(axis_id)
            ax.pos = ax_t.pos
            ax.vel = ax_t.vel
            ax.enabled = ax_t.enabled
            ax.fault = ax_t.fault
