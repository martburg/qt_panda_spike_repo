"""Qt renderer for DenSi compact limit fields."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QLineEdit

from .densi_limits_vm import DenSiLimitsVM
from ...qtutil.ui_update import set_enabled, set_text


def apply_densi_limits_vm(
    vm: DenSiLimitsVM,
    *,
    find_line_edit: Callable[[str], QLineEdit | None],
) -> None:
    for obj_name, txt in vm.texts.items():
        le = None
        try:
            le = find_line_edit(obj_name)
        except Exception:
            le = None
        if le is None:
            continue
        try:
            if le.text() == txt:
                # avoid repaint churn
                pass
            else:
                was = le.blockSignals(True)
                set_text(le, txt)
                le.blockSignals(was)
            # Ensure these are display-only on DenSi.
            set_enabled(le, False)
        except Exception:
            continue
