"""Qt-only modal lock helper for disabling and restoring widgets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from PySide6.QtWidgets import QLineEdit, QTabWidget, QWidget


@dataclass
class ModalLock:
    widgets: Iterable[QWidget]
    tabs: QTabWidget | None
    enable_widget: Callable[[QWidget, bool], None]
    enable_line_edit: Callable[[QLineEdit, bool], None]

    _locked: bool = False
    _prev_enabled: dict[QWidget, bool] = field(default_factory=dict)
    _prev_tabbar_enabled: bool | None = None

    def lock(self, allow: Iterable[QWidget] | None = None) -> None:
        if self._locked:
            return

        self._prev_enabled = {}
        if self.tabs is not None:
            self._prev_tabbar_enabled = bool(self.tabs.tabBar().isEnabled())
            self.enable_widget(self.tabs.tabBar(), False)

        for w in self.widgets:
            try:
                self._prev_enabled[w] = bool(w.isEnabled())
                self.enable_widget(w, False)
            except RuntimeError:
                continue

        for w in (allow or []):
            if isinstance(w, QLineEdit):
                self.enable_line_edit(w, True)
            else:
                self.enable_widget(w, True)

        self._locked = True

    def unlock(self) -> None:
        if not self._locked:
            return

        for w, was_enabled in list(self._prev_enabled.items()):
            try:
                if isinstance(w, QLineEdit):
                    self.enable_line_edit(w, bool(was_enabled))
                else:
                    self.enable_widget(w, bool(was_enabled))
            except RuntimeError:
                pass
        self._prev_enabled.clear()

        if self.tabs is not None and self._prev_tabbar_enabled is not None:
            self.enable_widget(self.tabs.tabBar(), bool(self._prev_tabbar_enabled))
        self._prev_tabbar_enabled = None
        self._locked = False
