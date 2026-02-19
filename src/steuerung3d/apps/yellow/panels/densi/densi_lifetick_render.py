"""Qt renderer for DenSi LifeTick UI (txtTick)."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit

from .densi_lifetick_vm import DenSiLifeTickVM
from ...qtutil.ui_update import set_text


def apply_densi_lifetick_vm(vm: DenSiLifeTickVM, *, txtTick: QLineEdit | None) -> None:
    if txtTick is None:
        return
    try:
        if txtTick.text() != vm.text:
            set_text(txtTick, vm.text)
    except Exception:
        pass
