"""Legacy PLC ';' delimited UDP codec (canonical: KommAnton__MAIN.st).

This module is an internal implementation façade.

Lane 1 refactor policy:
- keep public API stable (see :mod:`steuerung3d.protocol.plc_codec`)
- split large implementation into focused modules
- no semantic changes intended
"""

from __future__ import annotations

from steuerung3d.protocol.plc_codec_downlink import (
    DecodedDownlink,
    decode_downlink,
    encode_downlink,
)
from steuerung3d.protocol.plc_codec_fields import PARAM_KEYMAP as _PARAM_KEYMAP
from steuerung3d.protocol.plc_codec_uplink import (
    decode_uplink_to_snapshot,
    encode_uplink_from_snapshot,
)

__all__ = [
    "DecodedDownlink",
    "_PARAM_KEYMAP",
    "decode_downlink",
    "decode_uplink_to_snapshot",
    "encode_downlink",
    "encode_uplink_from_snapshot",
]
