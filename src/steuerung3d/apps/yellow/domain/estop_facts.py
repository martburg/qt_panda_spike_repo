"""Shared E-Stop decoding and facts (Qt-free)."""

from __future__ import annotations

from typing import Dict

from steuerung3d.protocol.estop_bits import (
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    decode_estop_word as _decode_estop_word,
    encode_estop_word as _encode_estop_word,
)


def decode_estop_word(word: int) -> Dict[str, bool]:
    return _decode_estop_word(int(word))


def encode_estop_word(bits: Dict[str, bool], *, base: int = 0) -> int:
    return int(_encode_estop_word(dict(bits), base=int(base)))


def estop_cause_keys() -> set[str]:
    return set(ESTOP_CAUSE_KEYS)


def estop_ok_keys() -> set[str]:
    return set(ESTOP_OK_KEYS)


def reset_able_from_word(word: int) -> bool:
    try:
        bits = decode_estop_word(int(word))
        return bool(bits.get("reset_able", False))
    except Exception:
        return False


def ready_from_word(word: int) -> bool:
    try:
        bits = decode_estop_word(int(word))
        return bool(bits.get("ready", False))
    except Exception:
        return False
