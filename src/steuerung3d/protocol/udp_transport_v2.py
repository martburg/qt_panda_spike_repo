from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.raw_controls import RawControls
from steuerung3d.protocol.transport import TransportV2
from steuerung3d.protocol.udp_channels import (
    UdpRawControlsIn, UdpRawControlsOut,
    UdpIntentIn, UdpIntentOut,
    UdpCommandIn, UdpCommandOut,
    UdpTelemetryIn, UdpTelemetryOut,
)


@dataclass
class UdpTransportV2(TransportV2):
    """A thin composition wrapper that exposes the full TransportV2 interface over UDP.

    Each stream direction is optional; calling a method that is not configured
    raises a RuntimeError with a clear message (helps debugging miswired stacks).
    """

    raw_in: Optional[UdpRawControlsIn] = None
    raw_out: Optional[UdpRawControlsOut] = None
    intent_in: Optional[UdpIntentIn] = None
    intent_out: Optional[UdpIntentOut] = None
    cmd_in: Optional[UdpCommandIn] = None
    cmd_out: Optional[UdpCommandOut] = None
    telem_in: Optional[UdpTelemetryIn] = None
    telem_out: Optional[UdpTelemetryOut] = None

    # --- raw controls ---
    def publish_raw_controls(self, rc: RawControls) -> None:
        if self.raw_out is None:
            raise RuntimeError("UdpTransportV2.raw_out not configured")
        self.raw_out.publish_raw_controls(rc)

    def drain_raw_controls(self, limit: int = 1000) -> List[RawControls]:
        if self.raw_in is None:
            raise RuntimeError("UdpTransportV2.raw_in not configured")
        return self.raw_in.drain_raw_controls(limit=limit)

    # --- intents ---
    def publish_intent(self, intent: Intent) -> None:
        if self.intent_out is None:
            raise RuntimeError("UdpTransportV2.intent_out not configured")
        self.intent_out.publish_intent(intent)

    def drain_intents(self, limit: int = 1000) -> List[Intent]:
        if self.intent_in is None:
            raise RuntimeError("UdpTransportV2.intent_in not configured")
        return self.intent_in.drain_intents(limit=limit)

    # --- command frames ---
    def publish_command_frame(self, frame: CommandFrame) -> None:
        if self.cmd_out is None:
            raise RuntimeError("UdpTransportV2.cmd_out not configured")
        self.cmd_out.publish_command_frame(frame)

    def drain_command_frames(self, limit: int = 1000) -> List[CommandFrame]:
        if self.cmd_in is None:
            raise RuntimeError("UdpTransportV2.cmd_in not configured")
        return self.cmd_in.drain_command_frames(limit=limit)

    # --- telemetry ---
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        if self.telem_out is None:
            raise RuntimeError("UdpTransportV2.telem_out not configured")
        self.telem_out.publish_telemetry(snap)

    def drain_telemetry(self, limit: int = 1000) -> List[TelemetrySnapshot]:
        if self.telem_in is None:
            raise RuntimeError("UdpTransportV2.telem_in not configured")
        return self.telem_in.drain_telemetry(limit=limit)
