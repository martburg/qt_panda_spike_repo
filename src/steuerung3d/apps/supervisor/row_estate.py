from __future__ import annotations

from steuerung3d.protocol.banner_estate import BANNER_DYNAMIC_EXCLUDE
from steuerung3d.protocol.estop_bits import ESTOP_CAUSE_KEYS, ESTOP_OK_KEYS, decode_estop_word


def estate_from_word(word: int) -> str:
    """Return supervisor estate from the estop word.

    This intentionally preserves the supervisor's local estate policy instead of
    delegating to the shared banner helper, because the supervisor row model
    treats brake-not-ok + released taster as IDLE rather than ESTOP.
    """

    w = int(word) & 0xFFFFFFFF
    if w == 0:
        return "ESTOP"
    bits = decode_estop_word(w)
    trip_cause = any(bool(bits.get(k, False)) for k in ESTOP_CAUSE_KEYS)
    ok_keys = [
        k
        for k in ESTOP_OK_KEYS
        if (k not in BANNER_DYNAMIC_EXCLUDE) and (k not in ("brk1_ok", "brk2_ok"))
    ]
    ok_chain_fault = any(not bool(bits.get(k, True)) for k in ok_keys)
    taster = bool(bits.get("taster", False))
    schuetz = bool(bits.get("schuetz", False))
    brk_ok = bool(bits.get("brk1_ok", True)) and bool(bits.get("brk2_ok", True))
    if trip_cause or ok_chain_fault or not schuetz:
        return "ESTOP"
    if not taster:
        return "IDLE"
    return "READY" if brk_ok else "ARMED"
