# src/steuerung3d/util/tick.py
from __future__ import annotations


def tick_delta_16(cur: int, prev: int) -> int:
    """Wrap-safe 16-bit delta (legacy PLC lifetick semantics)."""
    return (int(cur) - int(prev)) & 0xFFFF


def compute_time_tick(prev: int | None, cur: int) -> tuple[int, int]:
    """Return (delta, new_prev) for legacy TimeTick display.

    Legacy behavior: TimeTick shows how many device ticks elapsed between two
    successive telemetry updates received by the UI.
    """
    cur16 = int(cur) & 0xFFFF
    if prev is None:
        return 0, cur16
    return tick_delta_16(cur16, int(prev) & 0xFFFF), cur16
