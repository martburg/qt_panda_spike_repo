# src/steuerung3d/common/staleness.py
from __future__ import annotations


def age_ticks(now_tick: int, last_tick: int | None) -> int | None:
    """Return tick age (now - last) or None if last is unknown."""
    if last_tick is None:
        return None
    return int(now_tick) - int(last_tick)


def is_stale(now_tick: int, last_tick: int | None, max_age_ticks: int) -> bool:
    """Return True if last_tick is too old or unknown.

    Note: max_age_ticks is inclusive. Age == max_age_ticks is stale.
    """
    if last_tick is None:
        return True
    if int(max_age_ticks) <= 0:
        return True
    age = int(now_tick) - int(last_tick)
    return age >= int(max_age_ticks)
