from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from steuerung3d.core.telemetry import apply_measured_snapshot
from steuerung3d.protocol.transport import InMemTransportV2

from .edge import TwinCATLegacyWinchEdge


@dataclass
class TwinCATLegacyWinchEdgeDevice:
    """In-process adapter that drives a TwinCAT legacy edge instance.

    This preserves the `.step(state, cmd, dt)` device seam while using the
    TransportV2 edge under the hood.
    """

    axis_id: str
    plc_remote: Tuple[str, int]
    local_bind: Tuple[str, int]
    timeout_s: float = 0.02
    modus: str = "E"
    intent: bool = True
    dt_s: float = 0.01

    _transport: InMemTransportV2 = field(default_factory=InMemTransportV2)
    _edge: TwinCATLegacyWinchEdge | None = None

    def _ensure_edge(self) -> TwinCATLegacyWinchEdge:
        if self._edge is None:
            self._edge = TwinCATLegacyWinchEdge(
                axis_id=str(self.axis_id),
                transport=self._transport,
                plc_remote=self.plc_remote,
                local_bind=self.local_bind,
                timeout_s=float(self.timeout_s),
                dt_s=float(self.dt_s),
                modus=str(self.modus),
                intent=bool(self.intent),
            )
        return self._edge

    def step(self, state, cmd, dt: float) -> None:
        edge = self._ensure_edge()
        edge.dt_s = float(dt)
        self._transport.publish_command_frame(cmd)
        edge.step_once()
        for snap in self._transport.drain_telemetry(limit=10):
            apply_measured_snapshot(state, snap)

    def close(self) -> None:
        if self._edge is not None:
            self._edge.close()
            self._edge = None


@dataclass
class TwinCATLegacyWinchFleetEdge:
    """Composite adapter that steps multiple edge devices."""

    devices: List[TwinCATLegacyWinchEdgeDevice]

    def step(self, state, cmd, dt: float) -> None:
        for d in self.devices:
            d.step(state, cmd, dt)

    def close(self) -> None:
        for d in self.devices:
            d.close()
