from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget


class FloatingOverlay(QWidget):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(None)
        self._anchor = parent
        self.setObjectName("viewportFloatingOverlay")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#viewportFloatingOverlay {"
            " background-color: rgba(20, 24, 30, 185);"
            " border: 1px solid rgba(255, 255, 255, 110);"
            " border-radius: 6px;"
            " }"
            "#viewportFloatingOverlay QLabel { color: white; font-weight: 600; }"
            "#viewportOverlayValue { background: rgba(255, 255, 255, 235); }"
        )

        self.label = QLabel("Overlay", self)
        self.value = QLineEdit(self)
        self.value.setObjectName("viewportOverlayValue")
        self.value.setMinimumWidth(260)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        layout.addWidget(self.label)
        layout.addWidget(self.value, 1)

    def anchor_to(self, widget: QWidget) -> None:
        self._anchor = widget
        self.reposition()

    def reposition(self) -> None:
        if self._anchor is None:
            return
        anchor = self._anchor
        if not anchor.isVisible():
            self.hide()
            return
        margin = 12
        size = self.sizeHint()
        max_width = max(180, anchor.width() - (margin * 2))
        width = min(max_width, max(size.width(), 300))
        height = size.height()
        self.resize(width, height)
        top_left = anchor.mapToGlobal(QPoint(margin, margin))
        self.move(top_left)
        self.raise_()
        self.show()
