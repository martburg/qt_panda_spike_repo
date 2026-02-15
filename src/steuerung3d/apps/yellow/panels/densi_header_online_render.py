"""Qt-only renderer for DenSi header online dot."""

from __future__ import annotations

from collections.abc import Callable

from .densi_header_online_vm import DenSiHeaderOnlineVM


def apply_densi_header_online_vm(
    vm: DenSiHeaderOnlineVM,
    *,
    set_dot: Callable[[str, str | None], None],
) -> None:
    # Controller owns dot lookup + property/QSS wiring via set_dot.
    set_dot("dotHdrOnline", vm.dot_state)
