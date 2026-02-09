from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Optional

from steuerung3d.adapters.links.base import Link
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState

from .multi_plc_device import MultiPlcDevice
from .plc_codec import PlcCodec
from .plc_endpoint import PlcEndpoint
from .validate import validate_endpoints


@dataclass
class PlcDevice:
    """
    Deprecated single-endpoint PLC device adapter.

    Use MultiPlcDevice with PlcEndpoint(s) instead.

    This shim keeps existing code working by wrapping one endpoint into MultiPlcDevice.
    """
    link: Link
    codec: PlcCodec

    # diagnostics mirror
    last_rx_tick: Optional[int] = None

    def __post_init__(self) -> None:
        warnings.warn(
            "PlcDevice is deprecated; use PlcEndpoint + MultiPlcDevice",
            DeprecationWarning,
            stacklevel=2,
        )
        ep = PlcEndpoint(
            name="plc",
            axis_ids=list(self.codec.spec.axis_ids),
            link=self.link,
            codec=self.codec,
        )
        validate_endpoints([ep])
        self._multi = MultiPlcDevice(endpoints=[ep])
        self._ep = ep

    def step(self, state: MachineState, cmd: CommandFrame, dt: float) -> None:
        self._multi.step(state, cmd, dt)
        self.last_rx_tick = self._ep.last_rx_tick
