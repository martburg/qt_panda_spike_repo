"""Qt-only renderer for DenSi E-Stop dots."""

from __future__ import annotations

from collections.abc import Callable

from .densi_estop_dots_vm import DenSiEstopDotsVM


def apply_densi_estop_dots_vm(
    vm: DenSiEstopDotsVM,
    *,
    set_dot: Callable[[str, str | None], None],
) -> None:
    # Header dots are fixed names in VM.
    for dot_name, state in vm.header.items():
        set_dot(dot_name, state)

    # Diagnostic dots may include header dot names too; set all (idempotent).
    for dot_name, state in vm.dots.items():
        set_dot(dot_name, state)
