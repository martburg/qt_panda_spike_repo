from __future__ import annotations

"""PLC codec adapter (canonical).

This module provides the *adapter* interface used by the PLC edge layer:

  - encode_command_frame(CommandFrame) -> bytes
  - try_decode_telemetry(bytes) -> Optional[TelemetrySnapshot]

The previous implementation was a scaffold with a placeholder token layout.
As a declared Lane-2 change (RefOS), this now delegates to the canonical
implementation in :mod:`steuerung3d.protocol.plc_codec`, which mirrors
KommAnton__MAIN.st.

Important semantic note:
  The canonical PLC telegrams are *per axis endpoint* (e.g. Anton/Burt/...).
  Therefore, this adapter currently supports exactly one axis_id per endpoint.
"""

from dataclasses import dataclass
from typing import Optional

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot

from steuerung3d.protocol.plc_codec import decode_uplink_to_snapshot, encode_downlink

from .plc_config import PlcWireSpec


@dataclass
class PlcCodec:
    """Codec used by PlcEndpoint.

    Args:
        spec: Wire/format parameters and endpoint axis assignment.
              For the canonical PLC protocol, spec.axis_ids must contain exactly one axis.
    """

    spec: PlcWireSpec

    def _axis_name(self) -> str:
        axis_ids = list(getattr(self.spec, "axis_ids", []) or [])
        if len(axis_ids) != 1:
            raise ValueError(
                "Canonical PLC codec supports exactly one axis_id per endpoint; "
                f"got axis_ids={axis_ids}"
            )
        return str(axis_ids[0])

    # -----------------------
    # TX: core -> PLC
    # -----------------------
    def encode_command_frame(self, cmd: CommandFrame) -> bytes:
        axis_name = self._axis_name()
        return encode_downlink(
            axis_id=axis_name,
            frame=cmd,
            true_token=self.spec.true_token,
            false_token=self.spec.false_token,
        )

    # -----------------------
    # RX: PLC -> core
    # -----------------------
    def try_decode_telemetry(self, payload: bytes) -> Optional[TelemetrySnapshot]:
        # Canonical decoder is already best-effort and returns None on parse errors.
        return decode_uplink_to_snapshot(payload)
