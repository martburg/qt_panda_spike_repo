from __future__ import annotations

from steuerung3d.core.intents import RequestEstopReset
from steuerung3d.protocol.codec import decode_intent, encode_intent


def test_estop_reset_intent_roundtrip_includes_axis_id() -> None:
    intent = RequestEstopReset(axis_id="Anton", hip_id="hip-123")
    payload = encode_intent(intent)
    decoded = decode_intent(payload)

    assert isinstance(decoded, RequestEstopReset)
    assert decoded.axis_id == "Anton"
    assert decoded.hip_id == "hip-123"
