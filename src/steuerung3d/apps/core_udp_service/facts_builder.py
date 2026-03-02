from __future__ import annotations

from typing import List

from steuerung3d.core.joy_facts import extract_joy_facts
from steuerung3d.core.mode_aggregate import AggregateInputs, AxisSafetyFacts
from steuerung3d.protocol.banner_estate import derive_banner_estate_from_word
from steuerung3d.protocol.estop_bits import decode_estop_word


def build_aggregate_inputs(*, state, router, axis_ids: List[str], dt: float) -> AggregateInputs:
    stale_after_ms = int(
        float(getattr(state, "densi_offline_after_ticks", 200)) * float(dt) * 1000.0
    )
    joy = getattr(state, "joy", None)
    jf = extract_joy_facts(joy)

    facts: list[AxisSafetyFacts] = []
    reg = dict(getattr(state, "densi_registry", {}) or {})
    for axis_id in axis_ids:
        estop_word = router.last_dev_estop_word_by_axis.get(axis_id)
        estate = None
        if estop_word is not None:
            try:
                estate = derive_banner_estate_from_word(
                    int(estop_word), within_brake_grace=lambda: False
                )
            except Exception:
                estate = None

        axis_armed = None if estate is None else (str(estate).upper() in ("ARMED", "READY"))
        axis_ready = None if estate is None else (str(estate).upper() == "READY")

        bits = None
        axis_taster = None
        if estop_word is not None:
            try:
                bits = decode_estop_word(int(estop_word))
                axis_taster = bool(bits.get("taster", False))
            except Exception:
                bits = None
                axis_taster = None

        # Prefer a single helper for claim/lease resolution.
        try:
            owner = str(state.axis_owner(axis_id))
        except Exception:
            owner = ""

        age_ms = None
        d = reg.get(axis_id)
        if d is not None:
            last_seen_tick = int(getattr(d, "last_seen_core_tick", -1))
            if last_seen_tick >= 0:
                age_ticks = int(state.tick) - last_seen_tick
                age_ms = int(max(0, age_ticks) * float(dt) * 1000.0)

        facts.append(
            AxisSafetyFacts(
                axis_id=str(axis_id),
                in_scope=True,
                estop_bits=bits,
                axis_taster=axis_taster,
                axis_armed=axis_armed,
                axis_ready=axis_ready,
                axis_age_ms=age_ms,
                axis_owner=owner,
            )
        )

    return AggregateInputs(
        axes=facts,
        stale_after_ms=stale_after_ms,
        joy_deadman=jf.deadman,
        joy_select_hip=jf.select_hip,
        joy_soll_speed=jf.soll_speed,
    )
