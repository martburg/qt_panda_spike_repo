"""DenSi header online dot view-model (Qt-free).

Computes the state for the header 'Online' dot (dotHdrOnline).

Semantics are preserved from DenSiController._render_header_online_dot:
- dot off until at least one command frame is seen
- green while frames flow, amber when stale
"""

from __future__ import annotations

from dataclasses import dataclass

from ..controllers.ui_estop import age_to_online_state


@dataclass(frozen=True)
class DenSiHeaderOnlineVM:
    dot_state: str | None  # "good"|"warn"|"bad"|None


def compute_densi_header_online_vm(
    *,
    seen_first_cmd: bool,
    now_ns: int,
    last_cmd_ns: int | None,
    good_max_s: float = 1.0,
) -> DenSiHeaderOnlineVM:
    if not bool(seen_first_cmd):
        return DenSiHeaderOnlineVM(dot_state=None)

    last_ns = int(last_cmd_ns or 0)
    age_s = (int(now_ns) - last_ns) / 1e9 if last_ns else 1e9
    state = age_to_online_state(age=float(age_s), good_max=float(good_max_s), warn_max=None)
    return DenSiHeaderOnlineVM(dot_state=state)
