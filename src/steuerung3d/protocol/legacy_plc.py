"""Legacy Beckhoff PLC UDP protocol (semicolon-delimited ASCII).

This module is intentionally *dumb*: it only knows how to parse the wire format
into named fields (base + tail), following the exact field ordering used in the
PLC ST code (KommAnton__MAIN.st and siblings).

Higher layers (adapters/devices) can then map these fields into typed domain
objects like AxisTelemetry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

# Base uplink fields 0..37 (see legacy_plc_anton.md)
UPLINK_BASE_FIELDS: List[str] = [
    "OwnPID",
    "LifetickUItx",
    "Status",
    "GuideStatus",
    "PosIst",
    "SpeedIstUI",
    "MasterMomentUI",
    "CabTemperatureUI",
    "Name",
    "GearToUI",
    "PosMaxHardUI",
    "PosMaxUserUI",
    "PosMinUserUI",
    "PosMinHardUI",
    "SpeedMaxUI",
    "AccMaxUI",
    "DccMaxUI",
    "AmpMaxUI",
    "FilterP",
    "FilterI",
    "FilterD",
    "FilterIL",
    "RopeSWLL",
    "RopeDiameter",
    "RopeType",
    "RopeNumber",
    "RopeLength",
    "GuidePitchUI",
    "GuidePosMaxUI",
    "GuidePosMinUI",
    "GuidePosIstUI",
    "GuideIstSpeedUI",
    "MotAuslastUI",
    "ActCurUI",
    "SpeedMaxforUI",
    "PosDiffForUI",
    "RampenformUI",
    "EStopStatus",
]


# Tail fields appended after the EOD marker (see legacy_plc_anton.md)
UPLINK_TAIL_FIELDS: List[str] = [
    "SystemTime",
    "sCutPos",
    "sCutVel",
    "PosWinUI",
    "VelWinUI",
    "AccTotUI",
    "GuidePosManualMaxUI",
]


@dataclass(frozen=True)
class LegacyPlcUplink:
    """Parsed uplink message.

    - `fields` contains base uplink fields, keyed by the names above
    - `tail` contains tail fields after EOD (may be partially missing if message truncated)
    - `raw` keeps the original message for debugging/logging
    """

    fields: Dict[str, str]
    tail: Dict[str, str]
    raw: str

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.fields.get(key, self.tail.get(key, default)))  # type: ignore[arg-type]
        except Exception:
            return default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(float(self.fields.get(key, self.tail.get(key, default))))  # tolerate '12.0'
        except Exception:
            return default


def parse_uplink(message: str) -> LegacyPlcUplink:
    """Parse a PLC->controller uplink frame.

    The PLC usually emits a trailing ';' — we tolerate missing trailing delimiter.
    The EOD marker appears as a token 'EOD'.
    """
    raw = message
    # Split, keep ordering; tolerate stray whitespace/newlines.
    tokens = [t.strip() for t in message.strip().split(";")]

    # Drop empty token if message ended with ';'
    if tokens and tokens[-1] == "":
        tokens = tokens[:-1]

    # Find EOD marker
    try:
        eod_idx = tokens.index("EOD")
    except ValueError:
        # Some captures may include the original ST literal 'EOD\'
        try:
            eod_idx = tokens.index("EOD\\")
        except ValueError:
            # No EOD -> treat entire message as base (best-effort)
            eod_idx = len(tokens)

    base_tokens = tokens[:eod_idx]
    tail_tokens = tokens[eod_idx + 1 :] if eod_idx < len(tokens) else []

    # Map base fields (best-effort: ignore extra, missing -> absent)
    fields: Dict[str, str] = {}
    for i, name in enumerate(UPLINK_BASE_FIELDS):
        if i < len(base_tokens):
            fields[name] = base_tokens[i]

    tail: Dict[str, str] = {}
    for i, name in enumerate(UPLINK_TAIL_FIELDS):
        if i < len(tail_tokens):
            tail[name] = tail_tokens[i]

    return LegacyPlcUplink(fields=fields, tail=tail, raw=raw)


def encode_uplink(fields: Dict[str, object] | None = None, tail: Dict[str, object] | None = None) -> str:
    """Encode a PLC->controller uplink frame (semicolon-delimited ASCII).

    Notes:
    - Uses UPLINK_BASE_FIELDS and UPLINK_TAIL_FIELDS as the canonical ordering.
    - Ensures the frame contains the literal token "EOD\\" as a field.
    - Always ends with a trailing ';' (matches legacy behavior).
    """
    fields = dict(fields or {})
    tail = dict(tail or {})

    # Base fields
    parts: list[str] = []
    for k in UPLINK_BASE_FIELDS:
        v = fields.get(k, 0)
        if v is None:
            v = 0
        parts.append(str(v))

    # EOD marker (legacy uses a literal token containing a backslash)
    parts.append("EOD\\")

    # Tail fields
    for k in UPLINK_TAIL_FIELDS:
        v = tail.get(k, 0)
        if v is None:
            v = 0
        parts.append(str(v))

    return ";".join(parts) + ";"
