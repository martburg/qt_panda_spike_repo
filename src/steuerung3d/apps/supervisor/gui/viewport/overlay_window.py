from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class FloatingOverlay(QWidget):
    """Frameless companion window for native Panda viewport overlays.

    It follows an anchor widget because normal Qt child overlays do not sit
    reliably above a natively embedded Panda child window.
    """

    _MIN_ANCHOR_HEIGHT = 92
    _MIN_AVAILABLE_HEIGHT = 68
    _WIDTH_HEADROOM_FACTOR = 1.10

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(None)
        self._anchor: QWidget | None = parent
        self._last_geometry: tuple[int, int, int, int] | None = None
        self.setObjectName("supervisorViewportFloatingOverlay")
        window_types = cast(Any, Qt.WindowType)
        widget_attributes = cast(Any, Qt.WidgetAttribute)
        cast(Any, self).setWindowFlags(
            window_types.Tool | window_types.FramelessWindowHint | window_types.WindowStaysOnTopHint
        )
        cast(Any, self).setAttribute(widget_attributes.WA_ShowWithoutActivating, True)
        cast(Any, self).setAttribute(widget_attributes.WA_StyledBackground, True)
        cast(Any, self).setAttribute(widget_attributes.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            "#supervisorViewportFloatingOverlay {"
            " background-color: rgba(20, 24, 30, 185);"
            " border: 1px solid rgba(255, 255, 255, 110);"
            " border-radius: 6px;"
            " }"
            "#supervisorViewportFloatingOverlay QLabel { color: white; }"
            "#supervisorViewportOverlayLabel { font-weight: 600; }"
            "#supervisorViewportOverlayValue { color: rgba(245,245,245,220); }"
        )

        self.label = QLabel("Viewport", self)
        self.label.setObjectName("supervisorViewportOverlayLabel")
        self.value = QLabel("", self)
        self.value.setObjectName("supervisorViewportOverlayValue")
        cast(Any, self.value).setWordWrap(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        layout.addWidget(self.label)
        layout.addWidget(self.value, 1)

    def anchor_to(self, widget: QWidget) -> None:
        self._anchor = widget
        self.reposition(force_raise=False)

    def set_text(self, text: str) -> None:
        new_text = str(text)
        if self.value.text() == new_text:
            return
        self.value.setText(new_text)
        self._last_geometry = None
        self.reposition(force_raise=False)

    def reposition(self, *, force_raise: bool = False) -> None:
        anchor = self._anchor
        if anchor is None or not anchor.isVisible():
            self._last_geometry = None
            self.hide()
            return

        margin = 12
        if anchor.height() < self._MIN_ANCHOR_HEIGHT:
            self._last_geometry = None
            self.hide()
            return

        available_width = anchor.width() - (margin * 2)
        available_height = anchor.height() - (margin * 2)
        if available_height < self._MIN_AVAILABLE_HEIGHT:
            self._last_geometry = None
            self.hide()
            return

        size = self.sizeHint()
        overlay_width = max(220, size.width())
        required_viewport_width = int(overlay_width * self._WIDTH_HEADROOM_FACTOR)
        if available_width < required_viewport_width:
            self._last_geometry = None
            self.hide()
            return

        width = min(overlay_width, available_width)
        height = min(size.height(), max(40, available_height))
        top_left = anchor.mapToGlobal(QPoint(margin, margin))
        geometry = (int(top_left.x()), int(top_left.y()), int(width), int(height))
        geometry_changed = geometry != self._last_geometry
        self._last_geometry = geometry

        if geometry_changed:
            cast(Any, self).setGeometry(*geometry)
        if not self.isVisible():
            self.show()
            self.raise_()
        elif force_raise and geometry_changed:
            self.raise_()
