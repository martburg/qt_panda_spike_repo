"""HiP header dots view-model (Qt-free)."""

from __future__ import annotations

from typing import Callable

from ..domain.ui_estop import compute_header_estop_dot_states
from ..engines.hip.viewmodel import HipHeaderDots


def compute_hip_header_dots_vm(
    *,
    online_state: str | None,
    taster: bool,
    ready: bool,
    brk1_raw: bool,
    brk2_raw: bool,
    brake_ok_display: Callable[[bool], bool],
) -> HipHeaderDots:
    hdr_states = compute_header_estop_dot_states(
        taster=bool(taster),
        ready=bool(ready),
        brk1_raw=bool(brk1_raw),
        brk2_raw=bool(brk2_raw),
        brake_ok_display=brake_ok_display,
    )
    return HipHeaderDots(
        online_state=online_state,
        ready_state=hdr_states.get("dotHdrReady"),
        fbt_state=hdr_states.get("dotHdrFbt"),
        brk1_state=hdr_states.get("dotHdrBrake1"),
        brk2_state=hdr_states.get("dotHdrBrake2"),
    )
