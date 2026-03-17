from __future__ import annotations

import pytest

from steuerung3d.core.intents import RequestEstopReset
from steuerung3d.protocol.codec import decode_intent, encode_intent


def test_estop_reset_intent_roundtrip_includes_axis_id() -> None:
    intent = RequestEstopReset(axis_id="Anton", hip_id="hip-123", actor_kind="supervisor")
    payload = encode_intent(intent)
    decoded = decode_intent(payload)

    assert isinstance(decoded, RequestEstopReset)
    assert decoded.axis_id == "Anton"
    assert decoded.hip_id == "hip-123"


def test_estop_reset_intent_roundtrip_includes_actor_kind() -> None:
    intent = RequestEstopReset(axis_id="Anton", hip_id="sup", actor_kind="supervisor")
    payload = encode_intent(intent)
    decoded = decode_intent(payload)

    assert isinstance(decoded, RequestEstopReset)
    assert decoded.actor_kind == "supervisor"


def test_param_intent_decode_rejects_missing_axis_id() -> None:
    with pytest.raises(ValueError, match="param_write requires non-empty axis_id"):
        decode_intent({"type": "param_write", "group": "pos", "values": {"a": 1.0}})


def test_param_intent_ctor_rejects_blank_axis_id() -> None:
    from steuerung3d.core.intents import ParamEditBegin

    with pytest.raises(ValueError, match="param_edit_begin requires non-empty axis_id"):
        ParamEditBegin(axis_id="   ", hip_id="hip-123", group="pos")
