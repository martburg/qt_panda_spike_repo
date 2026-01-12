from __future__ import annotations

from dataclasses import dataclass
from typing import List

from steuerung3d.adapters.plc_twincat_legacy.device import TwinCATLegacyWinchUdpDevice


@dataclass
class TwinCATLegacyWinchFleetDevice:
    """
    Simple composite device that steps multiple TwinCAT legacy winch UDP devices.

    Rationale:
      - Each winch uses its own local UDP port on the controller.
      - We must send a lifetick every frame to every PLC (watchdog).
      - CoreEngine expects a single `.step(state, cmd, dt)` boundary.
    """

    devices: List[TwinCATLegacyWinchUdpDevice]

    def step(self, state, cmd, dt: float) -> None:
        for d in self.devices:
            d.step(state, cmd, dt)

    def close(self) -> None:
        for d in self.devices:
            d.close()

