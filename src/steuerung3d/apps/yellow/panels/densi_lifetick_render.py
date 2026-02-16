"""Qt renderer for DenSi LifeTick UI (txt_tick)."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit

from .densi_lifetick_vm import DenSiLifeTickVM
from ..controllers.ui_update import set_text


def apply_densi_lifetick_vm(vm: DenSiLifeTickVM, *, txt_tick: QLineEdit | None) -> None:
    if txt_tick is None:
        return
    try:
        if txt_tick.text() != vm.text:
            set_text(txt_tick, vm.text)
    except Exception:
        pass
