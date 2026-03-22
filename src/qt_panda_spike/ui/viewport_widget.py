from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QWidget

from ..backends.base import FrameImage, PickRequest, ViewportBackend
from ..backends.native_embed import NativeEmbedBackend
from ..backends.offscreen import OffscreenBackend
from .floating_overlay import FloatingOverlay
from .pick_log import PickLog
from .picking_coords import map_widget_to_image


class ViewportWidget(QFrame):
    picked = Signal(str)

    def __init__(
        self,
        backend_name: str,
        pick_log_path: str | Path,
        *,
        pick_debug: bool = False,
        show_dome: bool = False,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._backend_name = backend_name
        self._pick_debug = bool(pick_debug)
        self._pick_log = PickLog(pick_log_path) if self._pick_debug else None
        self._backend: ViewportBackend = self._build_backend(backend_name, pick_debug=self._pick_debug, show_dome=show_dome)
        self._backend_started = False
        self._last_mouse_pos: QPoint | None = None
        self._pixmap: QPixmap | None = None
        self._frame_size: tuple[int, int] | None = None
        self._display_rect = self.rect()

        self._ready_emitted = False

        self._floating_overlay: FloatingOverlay | None = None
        self._overlay_panel = self._build_overlay_panel()
        self._overlay_label = QLabel("Overlay", self._overlay_panel)
        self._overlay_value = QLineEdit(self._overlay_panel)
        self._overlay_value.setObjectName("viewportOverlayValue")
        self._overlay_value.setText(f"backend={backend_name} | waiting for viewport")
        self._overlay_value.setMinimumWidth(260)
        self._overlay_layout = QHBoxLayout(self._overlay_panel)
        self._overlay_layout.setContentsMargins(10, 8, 10, 8)
        self._overlay_layout.setSpacing(8)
        self._overlay_layout.addWidget(self._overlay_label)
        self._overlay_layout.addWidget(self._overlay_value, 1)
        self._overlay_panel.adjustSize()
        if self._backend_name == "native":
            self._floating_overlay = FloatingOverlay(self)
            self._floating_overlay.value.setText(self._overlay_value.text())
        self._reposition_overlay()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    @property
    def pick_log_path(self) -> Path | None:
        return None if self._pick_log is None else self._pick_log.path

    def _build_backend(self, backend_name: str, *, pick_debug: bool, show_dome: bool) -> ViewportBackend:
        if backend_name == "offscreen":
            return OffscreenBackend(show_dome=show_dome, pick_debug=pick_debug)
        return NativeEmbedBackend(show_dome=show_dome, pick_debug=pick_debug)

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        self._reposition_overlay()
        if not self._backend_started:
            self._backend.start(self)
            self._backend_started = True
            self._raise_overlay()
            self._emit_status("Pick: starting viewport")

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if self._backend_started:
            self._backend.resize(self.width(), self.height())
        self._recompute_display_rect()
        self._reposition_overlay()

    def moveEvent(self, event: Any) -> None:
        super().moveEvent(event)
        self._reposition_overlay()

    def hideEvent(self, event: Any) -> None:
        if self._floating_overlay is not None:
            self._floating_overlay.hide()
        super().hideEvent(event)

    def mousePressEvent(self, event: Any) -> None:
        self._last_mouse_pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.RightButton:
            self._handle_pick(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        current = event.position().toPoint()
        if self._last_mouse_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = current - self._last_mouse_pos
            self._backend.orbit(delta.x(), delta.y())
        self._last_mouse_pos = current
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        self._last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: Any) -> None:
        self._backend.zoom(float(event.angleDelta().y()))
        super().wheelEvent(event)

    def _build_overlay_panel(self) -> QWidget:
        panel = QWidget(self)
        panel.setObjectName("viewportOverlayPanel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setStyleSheet(
            "#viewportOverlayPanel {"
            " background-color: rgba(20, 24, 30, 185);"
            " border: 1px solid rgba(255, 255, 255, 110);"
            " border-radius: 6px;"
            " }"
            "#viewportOverlayPanel QLabel { color: white; font-weight: 600; }"
            "#viewportOverlayValue { background: rgba(255, 255, 255, 235); }"
        )
        if self._backend_name == "native":
            panel.hide()
        return panel

    def _reposition_overlay(self) -> None:
        panel = self._overlay_panel
        margin = 12
        size = panel.sizeHint()
        max_width = max(180, self.width() - (margin * 2))
        width = min(max_width, max(size.width(), 300))
        height = size.height()
        panel.setGeometry(margin, margin, width, height)
        if self._floating_overlay is not None:
            self._floating_overlay.reposition()
        self._raise_overlay()

    def _raise_overlay(self) -> None:
        if self._floating_overlay is not None:
            self._floating_overlay.raise_()
            return
        self._overlay_panel.raise_()
        self._overlay_label.raise_()
        self._overlay_value.raise_()

    def _emit_status(self, text: str) -> None:
        self._overlay_value.setText(text)
        if self._floating_overlay is not None:
            self._floating_overlay.value.setText(text)
        self._raise_overlay()
        self.picked.emit(text)

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        if self._pixmap is None:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        painter.drawPixmap(self._display_rect, self._pixmap)
        painter.end()

    def _tick(self) -> None:
        if not self._backend_started:
            return
        self._backend.step()
        if self._floating_overlay is not None:
            self._floating_overlay.reposition()
        self._raise_overlay()
        frame = self._backend.latest_frame()
        if frame is not None:
            self._update_pixmap(frame)
            self.update()
        if not self._ready_emitted and self._backend.is_ready():
            self._ready_emitted = True
            if self.pick_log_path is not None:
                self._emit_status(f"Pick: ready | debug log: {self.pick_log_path}")
            else:
                self._emit_status("Pick: ready")
        for status in self._backend.drain_status_messages():
            self._emit_status(status)

    def _update_pixmap(self, frame: FrameImage) -> None:
        self._frame_size = (frame.width, frame.height)
        image = QImage(frame.rgba_bytes, frame.width, frame.height, QImage.Format.Format_RGBA8888)
        flipped = image.mirrored(False, True)
        self._pixmap = QPixmap.fromImage(flipped.copy())
        self._recompute_display_rect()

    def _recompute_display_rect(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            self._display_rect = self.rect()
            return
        scaled = self._pixmap.size()
        scaled.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = max(0, (self.width() - scaled.width()) // 2)
        y = max(0, (self.height() - scaled.height()) // 2)
        self._display_rect = QRect(x, y, scaled.width(), scaled.height())

    def _handle_pick(self, event: Any) -> None:
        if not self._backend_started:
            self._emit_status("Pick: waiting for viewport")
            return

        widget_x = float(event.position().x())
        widget_y = float(event.position().y())
        if self._backend_name == "native":
            image_width = float(max(1, self.width()))
            image_height = float(max(1, self.height()))
            image_x = widget_x
            image_y = widget_y
        elif self._frame_size is None:
            self._emit_status("Pick: waiting for viewport")
            return
        else:
            mapped = map_widget_to_image(
                widget_x=widget_x,
                widget_y=widget_y,
                display_x=float(self._display_rect.x()),
                display_y=float(self._display_rect.y()),
                display_width=float(self._display_rect.width()),
                display_height=float(self._display_rect.height()),
                image_width=float(self._frame_size[0]),
                image_height=float(self._frame_size[1]),
            )
            if mapped is None:
                self._emit_status("Pick: outside image")
                return
            image_width = float(self._frame_size[0])
            image_height = float(self._frame_size[1])
            image_x = mapped.x
            image_y = mapped.y

        request = PickRequest(
            widget_x=widget_x,
            widget_y=widget_y,
            widget_width=float(max(1, self.width())),
            widget_height=float(max(1, self.height())),
            display_x=float(self._display_rect.x()),
            display_y=float(self._display_rect.y()),
            display_width=float(max(1, self._display_rect.width())),
            display_height=float(max(1, self._display_rect.height())),
            image_x=image_x,
            image_y=image_y,
            image_width=image_width,
            image_height=image_height,
        )

        report = self._backend.pick(request)
        if report is None:
            return
        if self._pick_log is not None:
            self._pick_log.append(
                {
                    "backend": self._backend_name,
                    "request": request.to_record(),
                    **report.debug_record,
                }
            )
        self._emit_status(report.status_text)

    def closeEvent(self, event: Any) -> None:
        self._backend.shutdown()
        self._ready_emitted = False
        if self._floating_overlay is not None:
            self._floating_overlay.close()
        super().closeEvent(event)
