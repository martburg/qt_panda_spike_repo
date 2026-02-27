from __future__ import annotations

from typing import Dict

from steuerung3d.core.state import MachineState


# PLC Modus 'w' expects the full parameter set on each write.
# We merge partial UI writes with last-known params to avoid zeroing untouched fields.
PLC_WRITE_KEYS = {
    "HardMax",
    "UserMax",
    "UserMin",
    "HardMin",
    "VelMax",
    "AccMax",
    "DccMax",
    "MaxAmp",
    "P",
    "I",
    "D",
    "IL",
    "RampForm",
    "Pitch",
    "PosMax",
    "PosMin",
    "PosWin",
    "VelWin",
    "AccMove",
    "VelMaxMot",
}


def merge_plc_write_values(state: MachineState, *, cleaned: Dict[str, float]) -> Dict[str, float]:
    """Merge partial UI param writes with last-known device params.

    Structural extraction; behavior stays identical to the previous inline logic.
    """

    wire_vals = {k: float(v) for k, v in (state.params or {}).items() if k in PLC_WRITE_KEYS}
    wire_vals.update({k: float(v) for k, v in cleaned.items()})
    return wire_vals
