from __future__ import annotations

from steuerung3d.apps.yellow.domain import estop_facts


def test_estop_word_decode_encode_roundtrip() -> None:
    bits = {
        "master": True,
        "g3_fb": True,
        "reset_able": False,
    }
    word = estop_facts.encode_estop_word(bits)
    decoded = estop_facts.decode_estop_word(word)
    assert decoded["master"] is True
    assert decoded["g3_fb"] is True
    assert decoded["reset_able"] is False


def test_estop_ready_and_reset_able() -> None:
    word = estop_facts.encode_estop_word({"reset_able": True, "ready": True})
    assert estop_facts.reset_able_from_word(word) is True
    assert estop_facts.ready_from_word(word) is True
