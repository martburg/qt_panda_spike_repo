# src/steuerung3d/apps/yellow/controllers/widget_cache.py
"""Tiny widget lookup cache for Yellow controllers.

Motivation
----------
Yellow controllers update many dots/fields on a periodic timer. Repeated
QObject.findChild() calls in those hot paths can become noticeable jitter,
especially when DEBUG logging is enabled or the machine is under load.

This helper keeps semantics unchanged (still returns None if missing) while
ensuring each widget lookup happens at most once per controller instance.

The cache deliberately stores *negative* lookups too, so missing widgets don't
trigger repeated tree walks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, TypeVar

from PySide6.QtWidgets import (
    QAbstractSlider,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QPushButton,
    QWidget,
)

T = TypeVar("T", bound=QWidget)

_MISSING = object()


@dataclass
class WidgetCache:
    root: QWidget
    _cache: dict[tuple[type, str], Any] = field(default_factory=dict)

    def get(self, cls: type[T], object_name: str) -> Optional[T]:
        """Return a cached child widget by class + objectName."""
        key = (cls, str(object_name))
        v = self._cache.get(key, _MISSING)
        if v is _MISSING:
            try:
                w = self.root.findChild(cls, str(object_name))
            except Exception:
                w = None
            self._cache[key] = w if (w is not None and isinstance(w, cls)) else None
            v = self._cache[key]
        return v if isinstance(v, cls) else None

    # Convenience typed accessors -------------------------------------------------

    def widget(self, object_name: str) -> Optional[QWidget]:
        return self.get(QWidget, object_name)

    def line_edit(self, object_name: str) -> Optional[QLineEdit]:
        return self.get(QLineEdit, object_name)

    def combo_box(self, object_name: str) -> Optional[QComboBox]:
        return self.get(QComboBox, object_name)

    def checkbox(self, object_name: str) -> Optional[QCheckBox]:
        return self.get(QCheckBox, object_name)

    def button(self, object_name: str) -> Optional[QPushButton]:
        return self.get(QPushButton, object_name)

    def slider(self, object_name: str) -> Optional[QAbstractSlider]:
        return self.get(QAbstractSlider, object_name)
