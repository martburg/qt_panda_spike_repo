from __future__ import annotations

from steuerung3d.apps.yellow.domain.ui_banner import (
    BANNER_DYNAMIC_EXCLUDE,
    derive_banner_estate_from_word,
)
from steuerung3d.protocol.estop_bits import (
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    ESTOP_SPECS,
    encode_estop_word,
)


def _healthy_bits() -> dict[str, bool]:
    """Build a logically-healthy E-Stop bits dict for encoding."""
    bits: dict[str, bool] = {}
    for k in ESTOP_SPECS.keys():
        if k in ESTOP_OK_KEYS:
            bits[k] = True
        elif k in ESTOP_CAUSE_KEYS:
            bits[k] = False
        else:
            bits[k] = False
    return bits


def test_banner_estate_word_zero_is_estop() -> None:
    assert derive_banner_estate_from_word(0, within_brake_grace=lambda: False) == "ESTOP"


def test_banner_estate_idle_armed_ready() -> None:
    bits = _healthy_bits()
    bits.update(
        {
            "schuetz": True,
            "taster": False,
            "brk1_ok": True,
            "brk2_ok": True,
        }
    )
    w = encode_estop_word(bits)
    assert derive_banner_estate_from_word(w, within_brake_grace=lambda: False) == "IDLE"

    # Taster ON, brakes not yet OK, but still within grace -> ARMED (not a trip)
    bits["taster"] = True
    bits["brk1_ok"] = False
    bits["brk2_ok"] = False
    w = encode_estop_word(bits)
    assert derive_banner_estate_from_word(w, within_brake_grace=lambda: True) == "ARMED"

    # Grace expired and brakes still not OK -> trip
    assert derive_banner_estate_from_word(w, within_brake_grace=lambda: False) == "ESTOP"

    # Brakes OK -> READY
    bits["brk1_ok"] = True
    bits["brk2_ok"] = True
    w = encode_estop_word(bits)
    assert derive_banner_estate_from_word(w, within_brake_grace=lambda: False) == "READY"


def test_banner_estate_trip_cause_forces_estop() -> None:
    bits = _healthy_bits()
    bits.update({"schuetz": True, "taster": True, "brk1_ok": True, "brk2_ok": True})
    # any trip-cause bit (e.g. master) forces ESTOP
    bits["master"] = True
    w = encode_estop_word(bits)
    assert derive_banner_estate_from_word(w, within_brake_grace=lambda: False) == "ESTOP"


def test_banner_estate_ok_chain_fault_forces_estop() -> None:
    bits = _healthy_bits()
    bits.update({"schuetz": True, "taster": False, "brk1_ok": True, "brk2_ok": True})

    ok_eval = sorted(
        k
        for k in ESTOP_OK_KEYS
        if (k not in BANNER_DYNAMIC_EXCLUDE) and (k not in ("brk1_ok", "brk2_ok"))
    )
    assert ok_eval, "expected at least one OK-key for banner evaluation"

    bits[ok_eval[0]] = False
    w = encode_estop_word(bits)
    assert derive_banner_estate_from_word(w, within_brake_grace=lambda: False) == "ESTOP"
