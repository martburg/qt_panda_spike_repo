"""Shared taster edge tracking for Yellow (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TasterEdgeState:
    prev: bool = False
    pressed_s: float | None = None


def update_taster_edge_state(*, state: TasterEdgeState, taster: bool, now_s: float) -> TasterEdgeState:
    prev = bool(state.prev)
    pressed_s = state.pressed_s
    if (not prev) and bool(taster):
        pressed_s = float(now_s)
    return TasterEdgeState(prev=bool(taster), pressed_s=pressed_s)


def within_brake_grace(*, state: TasterEdgeState, now_s: float, grace_s: float) -> bool:
    t0 = state.pressed_s
    if t0 is None:
        return False
    return (float(now_s) - float(t0)) <= float(grace_s)
