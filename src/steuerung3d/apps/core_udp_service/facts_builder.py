from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from steuerung3d.core.joy_facts import extract_joy_facts
from steuerung3d.core.mode_aggregate import AggregateInputs, AxisSafetyFacts
from steuerung3d.protocol.banner_estate import derive_banner_estate_from_word
from steuerung3d.protocol.estop_bits import decode_estop_word


class _RegistryEntryLike(Protocol):
    @property
    def last_seen_core_tick(self) -> int: ...


class _AggregateStateLike(Protocol):
    @property
    def tick(self) -> int: ...

    @property
    def joy(self) -> object | None: ...

    @property
    def densi_registry(self) -> Mapping[str, _RegistryEntryLike]: ...

    @property
    def densi_offline_after_ticks(self) -> int: ...

    def axis_owner(self, axis_id: str) -> str | None: ...


class _RouterLike(Protocol):
    @property
    def last_dev_estop_word_by_axis(self) -> Mapping[str, int]: ...


def _coerce_registry(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _safe_axis_owner(*, state: _AggregateStateLike, axis_id: str) -> str:
    try:
        return str(state.axis_owner(axis_id) or "")
    except Exception:
        return ""


def _entry_age_ms(*, entry: object, now_tick: int, dt: float) -> int | None:
    last_seen_raw = getattr(entry, "last_seen_core_tick", -1)
    try:
        last_seen_tick = int(last_seen_raw)
    except Exception:
        return None
    if last_seen_tick < 0:
        return None
    age_ticks = now_tick - last_seen_tick
    return int(max(0, age_ticks) * float(dt) * 1000.0)


def build_aggregate_inputs(
    *,
    state: _AggregateStateLike,
    router: _RouterLike,
    axis_ids: Sequence[str],
    dt: float,
) -> AggregateInputs:
    stale_after_ms = int(float(state.densi_offline_after_ticks) * float(dt) * 1000.0)
    jf = extract_joy_facts(state.joy)

    facts: list[AxisSafetyFacts] = []
    reg = _coerce_registry(state.densi_registry)
    for axis_id_raw in axis_ids:
        axis_id = str(axis_id_raw)
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

        owner = _safe_axis_owner(state=state, axis_id=axis_id)

        age_ms = _entry_age_ms(entry=reg.get(axis_id), now_tick=int(state.tick), dt=dt)

        facts.append(
            AxisSafetyFacts(
                axis_id=axis_id,
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
