"""Qt-only estop rendering helpers for Hip panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, cast

from PySide6.QtWidgets import QCheckBox, QPushButton

from ...qtutil.ui_update import set_checked, set_enabled


@dataclass(frozen=True)
class HipEstopBindings:
    btn_estop_reset: QPushButton | None
    estop_checks: dict[str, QCheckBox]
    set_dot: Callable[[str, str], None]


def _active_keys(value: object) -> set[str]:
    if isinstance(value, set):
        items = cast(set[object], value)
        return {str(k) for k in items}
    if isinstance(value, list):
        items = cast(list[object], value)
        return {str(k) for k in items}
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return {str(k) for k in items}
    return set()


def apply_hip_estop(bindings: HipEstopBindings, vm: Any) -> None:
    es = getattr(vm, "estop_state", None)
    if es is None:
        return

    for dot, state in dict(getattr(es, "dots", {}) or {}).items():
        bindings.set_dot(str(dot), str(state))
    if bindings.btn_estop_reset is not None:
        set_enabled(bindings.btn_estop_reset, bool(es.reset_enabled))

    for key, cb in (bindings.estop_checks or {}).items():
        checkbox_states = dict(getattr(es, "checkbox_states", {}) or {})
        v = bool(checkbox_states.get(key, False))
        set_checked(cb, v, block_signals=True)
        if bool(getattr(es, "profile_changed", False)):
            try:
                f = cb.font()
                active_keys = _active_keys(getattr(es, "active_keys", None))
                f.setBold(key in active_keys)
                cb.setFont(f)
            except Exception:
                pass
