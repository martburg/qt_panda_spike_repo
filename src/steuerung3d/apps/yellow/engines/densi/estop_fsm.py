"""E-Stop state machine helpers for DenSi engine (Qt-free)."""

from __future__ import annotations

from typing import Callable

from ...domain import estop_facts
from ...domain.banner_facts import BANNER_DYNAMIC_EXCLUDE, derive_banner_estate_from_word
from ...domain.estop_facts import (
    decode_estop_word,
    encode_estop_word,
    estop_cause_keys,
    estop_ok_keys,
)
from .types import EStopState


# compat
def reset_able_from_estop_word(word: int) -> bool:
    """Compatibility wrapper: use domain.estop_facts instead."""
    return bool(estop_facts.reset_able_from_word(int(word)))


# compat
def ready_from_estop_word(word: int) -> bool:
    """Compatibility wrapper: use domain.estop_facts instead."""
    return bool(estop_facts.ready_from_word(int(word)))


def derive_estop_inputs(inj_estop_word: int) -> tuple[int, bool, bool]:
    word = int(inj_estop_word)
    reset_able = bool(estop_facts.reset_able_from_word(word))
    ready_for_sollvel = bool(estop_facts.ready_from_word(word))
    return word, reset_able, ready_for_sollvel


def sync_reset_able_bit(
    *,
    inj_bits: dict[str, bool],
    inj_estop_word: int,
    within_brake_grace: Callable[[], bool],
) -> tuple[bool, int]:
    if "reset_able" not in inj_bits:
        return False, int(inj_estop_word)

    cause_keys = estop_cause_keys()
    ok_keys = estop_ok_keys()
    trip_causes = any(bool(inj_bits.get(k, False)) for k in cause_keys)

    try:
        estate = derive_banner_estate_from_word(
            int(inj_estop_word),
            within_brake_grace=within_brake_grace,
        )
    except Exception:
        estate = "ESTOP"
    in_estop = (estate == "ESTOP")

    desired = (not trip_causes) and bool(in_estop)
    if bool(inj_bits.get("reset_able", False)) == bool(desired):
        return False, int(inj_estop_word)

    inj_bits["reset_able"] = bool(desired)
    new_word = int(encode_estop_word(inj_bits))
    return True, new_word


def apply_estop_state_machine(
    *,
    inj_bits: dict[str, bool],
    state_t_s: float,
    brake_switch_s: float,
    brake_handoff_grace_s: float,
    estop_latched: bool,
    safety_ok: bool,
    taster_prev: bool,
    taster_rise_t_s: float | None,
    drive_ready: bool,
    estate: EStopState,
    brake_override_b1: bool,
    brake_override_b2: bool,
) -> tuple[int, bool, float | None, bool, EStopState, bool]:
    cause_keys = estop_cause_keys()
    ok_keys_all = estop_ok_keys()
    schuetz = bool(inj_bits.get("schuetz", False))
    taster = bool(inj_bits.get("taster", False))

    if taster and (not bool(taster_prev)):
        taster_rise_t_s = float(state_t_s)
    if not taster:
        taster_rise_t_s = None
    taster_prev = bool(taster)

    elapsed: float | None = None
    if taster_rise_t_s is not None:
        try:
            elapsed = float(state_t_s) - float(taster_rise_t_s)
        except Exception:
            elapsed = None

    brake_switch_s = float(brake_switch_s)
    grace_s = float(brake_handoff_grace_s)

    if bool(estop_latched) or (not schuetz):
        desired_brk_ok = (not taster)
    else:
        if not taster:
            desired_brk_ok = True
        else:
            desired_brk_ok = (elapsed is not None) and (elapsed >= brake_switch_s)

    for k in ("brk1_ok", "brk2_ok"):
        if k in inj_bits and bool(inj_bits.get(k, False)) != bool(desired_brk_ok):
            if k == "brk1_ok" and bool(brake_override_b1):
                continue
            if k == "brk2_ok" and bool(brake_override_b2):
                continue
            inj_bits[k] = bool(desired_brk_ok)

    trip_cause = any(bool(inj_bits.get(k, False)) for k in cause_keys)
    ok_keys = [
        k
        for k in ok_keys_all
        if (k not in BANNER_DYNAMIC_EXCLUDE) and (k not in ("brk1_ok", "brk2_ok"))
    ]
    ok_chain_fault = any(not bool(inj_bits.get(k, True)) for k in ok_keys)

    brk_ok = bool(inj_bits.get("brk1_ok", True)) and bool(inj_bits.get("brk2_ok", True))
    if taster:
        brake_trip = (not brk_ok) and ((elapsed is None) or (elapsed >= grace_s))
    else:
        brake_trip = (not brk_ok)

    trip_active = trip_cause or ok_chain_fault or brake_trip or (not bool(safety_ok))

    if trip_active:
        estop_latched = True
        if bool(inj_bits.get("ready", False)):
            inj_bits["ready"] = False
        if bool(inj_bits.get("schuetz", False)):
            inj_bits["schuetz"] = False
        drive_ready = False
        estate = EStopState.ESTOP
    else:
        if not schuetz:
            estate = EStopState.ESTOP
        elif not taster:
            estate = EStopState.IDLE
        else:
            estate = EStopState.READY if brk_ok else EStopState.ARMED

        desired_ready = (estate == EStopState.READY)
        if "ready" in inj_bits and bool(inj_bits.get("ready", False)) != bool(desired_ready):
            inj_bits["ready"] = bool(desired_ready)
        drive_ready = bool(desired_ready)

    inj_estop_word = int(encode_estop_word(inj_bits))
    return inj_estop_word, taster_prev, taster_rise_t_s, drive_ready, estate, estop_latched


def compute_estop_edge_and_update_state(
    *,
    estate: EStopState,
    prev_estop_state: bool,
    estop_word: int,
    state,
) -> bool:
    state.estop = bool(estate == EStopState.ESTOP)
    state.estop_status_word = int(estop_word)
    return bool(state.estop) and (not bool(prev_estop_state))
