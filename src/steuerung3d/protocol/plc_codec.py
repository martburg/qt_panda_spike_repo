"""Legacy PLC ';' delimited UDP codec (public API).

Implementation details live in :mod:`steuerung3d.protocol.plc_codec_impl`.

Lane 1 refactor: no semantic changes; public imports stay stable.
"""

from __future__ import annotations

from steuerung3d.protocol.plc_codec_impl import (
    _PARAM_KEYMAP,
    DecodedDownlink,
    decode_downlink,
    decode_uplink_to_snapshot,
    encode_downlink,
    encode_uplink_from_snapshot,
)

__all__: tuple[str, ...] = (
    "DecodedDownlink",
    "_PARAM_KEYMAP",
    "decode_downlink",
    "decode_uplink_to_snapshot",
    "encode_downlink",
    "encode_uplink_from_snapshot",
)
