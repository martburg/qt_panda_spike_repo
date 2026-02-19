"""Qt-only estop rendering helpers for Hip panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QCheckBox, QPushButton

from ..qtutil.ui_update import set_checked, set_enabled


@dataclass(frozen=True)
class HipEstopBindings:
    btn_estop_reset: QPushButton | None
    estop_checks: dict[str, QCheckBox]
    set_dot: Callable[[str, str], None]


def apply_hip_estop(bindings: HipEstopBindings, vm) -> None:
    es = getattr(vm, "estop_state", None)
    if es is None:
        return

    for dot, state in (es.dots or {}).items():
        bindings.set_dot(str(dot), state)
    if bindings.btn_estop_reset is not None:
        set_enabled(bindings.btn_estop_reset, bool(es.reset_enabled))

    for key, cb in (bindings.estop_checks or {}).items():
        v = bool(es.checkbox_states.get(key, False))
        set_checked(cb, v, block_signals=True)
        if es.profile_changed:
            try:
                f = cb.font()
                f.setBold(key in es.active_keys)
                cb.setFont(f)
            except Exception:
                pass
