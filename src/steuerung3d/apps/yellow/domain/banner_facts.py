# src/steuerung3d/apps/yellow/domain/banner_facts.py
"""Qt-free banner estate decoding facts."""

from __future__ import annotations

from collections.abc import Callable

from steuerung3d.protocol.estop_bits import (
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    decode_estop_word,
)


# These bits are dynamic/transient and should NOT be used to decide whether the
# OK-chain is tripped.
#
# IMPORTANT: keep this as a *superset* of what legacy controllers excluded.
# Excluding an extra key is only meaningful if that key is part of ESTOP_OK_KEYS.
BANNER_DYNAMIC_EXCLUDE: set[str] = {
    "ready",
    "taster",
    "schuetz",
    "reset_able",
    "steuerwort",
    # legacy names kept for backwards compatibility (not present in current specs)
    "key1_ok",
    "key2_ok",
    # physical key switches (present in specs, but not part of ESTOP_OK_KEYS)
    "schluessel1",
    "schluessel2",
}


def derive_banner_estate_from_word(
    word: int,
    *,
    within_brake_grace: Callable[[], bool] | None = None,
    dynamic_exclude: set[str] = BANNER_DYNAMIC_EXCLUDE,
) -> str:
    """Return one of: ESTOP | IDLE | ARMED | READY.

    The estate is computed from decoded logical bits:

    - Any trip cause -> ESTOP
    - Any OK-chain fault (excluding dynamic keys + brake bits) -> ESTOP
    - Brake mismatch -> ESTOP only after grace when taster is ON
    - Otherwise ladder:
        - schuetz=0 -> ESTOP
        - taster=0  -> IDLE
        - brk_ok=0  -> ARMED
        - brk_ok=1  -> READY
    """

    w = int(word) & 0xFFFFFFFF
    if w == 0:
        return "ESTOP"

    bits = decode_estop_word(w)

    # Trip cause bits always force ESTOP
    trip_cause = any(bool(bits.get(k, False)) for k in ESTOP_CAUSE_KEYS)

    # OK-chain trip evaluation: exclude dynamic bits and handle brake bits separately
    ok_keys = [
        k
        for k in ESTOP_OK_KEYS
        if (k not in dynamic_exclude) and (k not in ("brk1_ok", "brk2_ok"))
    ]
    ok_chain_fault = any(not bool(bits.get(k, True)) for k in ok_keys)

    taster = bool(bits.get("taster", False))
    schuetz = bool(bits.get("schuetz", False))
    brk_ok = bool(bits.get("brk1_ok", True)) and bool(bits.get("brk2_ok", True))

    # Brake bits:
    # - When taster is ON: trip only after grace
    # - When taster is OFF: immediate trip (brakes should be applied & watchers OK)
    if taster:
        grace = bool(within_brake_grace() if within_brake_grace is not None else False)
        brake_trip = (not brk_ok) and (not grace)
    else:
        brake_trip = not brk_ok

    if trip_cause or ok_chain_fault or brake_trip:
        return "ESTOP"

    # Ladder: Schuetz -> IDLE, Taster -> ARMED, Brakes lifted -> READY
    if not schuetz:
        return "ESTOP"
    if not taster:
        return "IDLE"
    return "READY" if brk_ok else "ARMED"
