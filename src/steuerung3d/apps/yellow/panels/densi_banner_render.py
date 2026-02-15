"""Qt-only renderer for DenSi banner."""

from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtWidgets import QLineEdit

from ..controllers.ui_update import set_text
from .densi_banner_vm import DenSiBannerVM


@dataclass
class DenSiBannerBindings:
    left: QLineEdit | None
    right: QLineEdit | None


def apply_densi_banner_vm(vm: DenSiBannerVM, b: DenSiBannerBindings) -> None:
    style = f"background-color: {vm.bg}; color: {vm.fg}; font-weight: 700;"
    for w in (b.left, b.right):
        if w is None:
            continue
        set_text(w, vm.estate)
        w.setStyleSheet(style)
