from __future__ import annotations

from steuerung3d.core.control_context import ControlContext
from steuerung3d.protocol.codec import decode_control_context, encode_control_context


def test_control_context_codec_roundtrip() -> None:
    ctx = ControlContext(seq=7, mode="independent_axes", input_mapping="axis_rate", motion_enabled=True)
    assert decode_control_context(encode_control_context(ctx)) == ctx
