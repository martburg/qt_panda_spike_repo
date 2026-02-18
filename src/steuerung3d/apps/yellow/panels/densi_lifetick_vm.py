"""DenSi LifeTick UI VM (txtTick).

Semantics:
- Show diff = (lifetick_tx - lifetick_rx) & 0xFFFF for the primary axis.
- If axis or meta missing -> "--".
"""

from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.core.state import MachineState


@dataclass(frozen=True)
class DenSiLifeTickVM:
    text: str  # already formatted


def compute_densi_lifetick_vm(*, state: MachineState, axis_id: str) -> DenSiLifeTickVM:
    if not axis_id:
        return DenSiLifeTickVM(text="--")
    ax = state.axes.get(axis_id)
    if ax is None:
        return DenSiLifeTickVM(text="--")
    try:
        tx = int(ax.meta.get("lifetick_tx", 0)) & 0xFFFF
    except Exception:
        tx = 0
    try:
        rx = int(ax.meta.get("lifetick_rx", 0)) & 0xFFFF
    except Exception:
        rx = 0
    diff = (tx - rx) & 0xFFFF
    return DenSiLifeTickVM(text=str(int(diff)))
