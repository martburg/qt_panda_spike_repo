"""Legacy PLC uplink codec (PLC -> Controller).

Split out of plc_codec_impl.py as a Lane-1 refactor (no semantic changes).
"""

from __future__ import annotations

from typing import Optional

from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.plc_codec_uplink_support import (
    decode_snapshot_from_payload,
    encode_snapshot_to_uplink,
)


def decode_uplink_to_snapshot(payload: bytes) -> Optional[TelemetrySnapshot]:
    """Decode one PLC uplink telegram into a TelemetrySnapshot."""
    return decode_snapshot_from_payload(payload)


def encode_uplink_from_snapshot(snap: TelemetrySnapshot, *, axis_name: str) -> bytes:
    """Encode a minimal but ST-compatible uplink telegram from a TelemetrySnapshot."""
    return encode_snapshot_to_uplink(snap, axis_name=axis_name)
