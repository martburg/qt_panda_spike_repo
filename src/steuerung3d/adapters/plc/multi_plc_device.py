from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.core.rig_logic import note_densi_seen

from .plc_endpoint import PlcEndpoint


@dataclass
class MultiPlcDevice:
    """
    Device adapter that supports N PLC endpoints with mixed axis assignments.

    Per tick:
      1) TX: send one UDP datagram (or other link frame) per endpoint
      2) RX: drain each endpoint; keep only the latest telemetry snapshot per endpoint
      3) Merge: apply measured axis values into MachineState

    Policy (v0.1 default):
      - Global estop/fault = OR across latest received endpoint snapshots this tick.
        (Safe: any PLC estop trips global)
      - core_mode is core-owned: we do NOT overwrite state.core_mode from PLC telemetry.
    """
    endpoints: list[PlcEndpoint]

    # diagnostics
    last_rx_tick_by_endpoint: Dict[str, Optional[int]] = None

    def __post_init__(self) -> None:
        if self.last_rx_tick_by_endpoint is None:
            self.last_rx_tick_by_endpoint = {e.name: None for e in self.endpoints}

    def step(self, state: MachineState, cmd: CommandFrame, dt: float) -> None:
        # --- TX fan-out ---
        for ep in self.endpoints:
            ep.send(cmd)

        # --- RX fan-in (latest wins per endpoint) ---
        latest_by_ep: Dict[str, TelemetrySnapshot] = {}
        for ep in self.endpoints:
            snap = ep.poll_latest(limit=100)
            if snap is not None:
                latest_by_ep[ep.name] = snap
                self.last_rx_tick_by_endpoint[ep.name] = snap.tick

        if not latest_by_ep:
            return

        # --- merge global flags (safe OR) ---
        # Only consider snapshots actually received this step.
        state.estop = any(s.estop for s in latest_by_ep.values())
        state.fault = any(s.fault for s in latest_by_ep.values())

        # --- merge axis measurements ---
        # Only update the axes included in each snapshot.
        for snap in latest_by_ep.values():
            for axis_id, ax_t in snap.axes.items():
                ax = state.ensure_axis(axis_id)
                note_densi_seen(state, axis_id, device_tick=int(getattr(snap, "tick", 0)))
                ax.pos = ax_t.pos
                ax.vel = ax_t.vel
                ax.enabled = ax_t.enabled
                ax.fault = ax_t.fault
