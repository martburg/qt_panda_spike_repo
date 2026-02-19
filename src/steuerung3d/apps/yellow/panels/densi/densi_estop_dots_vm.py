"""DenSi E-Stop dots view-model (Qt-free).

Computes:
- header dots (FBT/READY/BRAKE1/BRAKE2)
- per-bit diagnostic dots (dotMaster, dotG1Fb, ...)

This intentionally does NOT touch checkboxes; checkbox sync stays in the controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from ...domain.ui_estop import compute_estop_dot_states, compute_header_estop_dot_states
from steuerung3d.protocol.estop_bits import iter_specs


@dataclass(frozen=True)
class DenSiEstopDotsVM:
    header: dict[str, str]
    dots: dict[str, str | None]


def compute_densi_estop_dots_vm(
    *,
    bits: dict[str, bool],
    taster: bool,
    ready: bool,
    within_brake_grace: bool,
) -> DenSiEstopDotsVM:
    def brake_ok_display(raw: bool) -> bool:
        # Match DenSiController._brake_ok_display_disp
        if bool(taster) and bool(within_brake_grace):
            return True
        return bool(raw)

    hdr = compute_header_estop_dot_states(
        taster=bool(taster),
        ready=bool(ready),
        brk1_raw=bool(bits.get("brk1_ok", False)),
        brk2_raw=bool(bits.get("brk2_ok", False)),
        brake_ok_display=brake_ok_display,
    )
    states = compute_estop_dot_states(
        bits=bits,
        taster=bool(taster),
        specs=iter_specs(),
        brake_ok_display=brake_ok_display,
    )
    return DenSiEstopDotsVM(header=hdr, dots=states)
