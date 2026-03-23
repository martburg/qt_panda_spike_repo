# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportCallIssue=false
from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple, cast

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Signal
from qt_panda_spike.backends.base import FrameImage, PickRequest, ViewportBackend
from qt_panda_spike.backends.offscreen import OffscreenBackend
from qt_panda_spike.ui.pick_log import PickLog
from qt_panda_spike.ui.picking_coords import map_widget_to_image

from qt_panda_spike.backends.native_embed import NativeEmbedBackend


class _DisplayRect(NamedTuple):
    x: int
    y: int
    width: int
    height: int


class ViewportWidget(QtWidgets.QFrame):
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
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        widget_attr = None
        qt_obj = QtCore.Qt
        if hasattr(qt_obj, "WA_NativeWindow"):
            widget_attr = qt_obj.WA_NativeWindow
        elif hasattr(qt_obj, "WidgetAttribute"):
            widget_attr = getattr(qt_obj.WidgetAttribute, "WA_NativeWindow", None)
        if widget_attr is not None:
            cast(Any, self).setAttribute(widget_attr)
        focus_policy = None
        if hasattr(qt_obj, "StrongFocus"):
            focus_policy = qt_obj.StrongFocus
        elif hasattr(qt_obj, "FocusPolicy"):
            focus_policy = getattr(qt_obj.FocusPolicy, "StrongFocus", None)
        if focus_policy is not None:
            cast(Any, self).setFocusPolicy(focus_policy)

        self._backend_name = backend_name
        self._pick_debug = bool(pick_debug)
        self._pick_log: PickLog | None = PickLog(pick_log_path) if self._pick_debug else None
        self._backend: ViewportBackend = self._build_backend(
            backend_name,
            pick_debug=self._pick_debug,
            show_dome=show_dome,
        )
        self._backend_started = False
        self._last_mouse_pos: Any | None = None
        self._pixmap: Any | None = None
        self._frame_size: tuple[int, int] | None = None
        self._display_rect = _DisplayRect(0, 0, 0, 0)
        self._ready_emitted = False

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    @property
    def pick_log_path(self) -> Path | None:
        return None if self._pick_log is None else self._pick_log.path

    def _build_backend(
        self, backend_name: str, *, pick_debug: bool, show_dome: bool
    ) -> ViewportBackend:
        if backend_name == "offscreen":
            return OffscreenBackend(show_dome=show_dome, pick_debug=pick_debug)
        return NativeEmbedBackend(show_dome=show_dome, pick_debug=pick_debug)

    def showEvent(self, event: Any) -> None:
        cast(Any, super()).showEvent(event)
        if not self._backend_started:
            self._backend.start(self)
            self._backend_started = True
            self._emit_status("Pick: starting viewport")

    def resizeEvent(self, event: Any) -> None:
        cast(Any, super()).resizeEvent(event)
        if self._backend_started:
            self._backend.resize(self.width(), self.height())
        self._recompute_display_rect()

    def mousePressEvent(self, event: Any) -> None:
        self._last_mouse_pos = event.position().toPoint()
        if event.button() == cast(Any, QtCore.Qt.MouseButton).RightButton:
            self._handle_pick(event)
            event.accept()
            return
        cast(Any, super()).mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        current = event.position().toPoint()
        if (
            self._last_mouse_pos is not None
            and event.buttons() & cast(Any, QtCore.Qt.MouseButton).LeftButton
        ):
            delta = current - self._last_mouse_pos
            self._backend.orbit(float(delta.x()), float(delta.y()))
        self._last_mouse_pos = current
        cast(Any, super()).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        self._last_mouse_pos = None
        cast(Any, super()).mouseReleaseEvent(event)

    def wheelEvent(self, event: Any) -> None:
        self._backend.zoom(float(event.angleDelta().y()))
        cast(Any, super()).wheelEvent(event)

    def _emit_status(self, text: str) -> None:
        self.picked.emit(text)

    def paintEvent(self, event: Any) -> None:
        cast(Any, super()).paintEvent(event)
        if self._pixmap is None:
            return
        painter = QtGui.QPainter(self)
        cast(Any, painter).fillRect(cast(Any, self).rect(), cast(Any, self).palette().window())
        target = QtCore.QRect(
            self._display_rect.x,
            self._display_rect.y,
            self._display_rect.width,
            self._display_rect.height,
        )
        cast(Any, painter).drawPixmap(target, self._pixmap)
        painter.end()

    def _tick(self) -> None:
        if not self._backend_started:
            return
        self._backend.step()
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
        image = QtGui.QImage(
            frame.rgba_bytes,
            frame.width,
            frame.height,
            cast(Any, QtGui.QImage).Format.Format_RGBA8888,
        )
        flipped = image.mirrored(False, True)
        self._pixmap = cast(Any, QtGui.QPixmap).fromImage(cast(Any, flipped).copy())
        self._recompute_display_rect()

    def _recompute_display_rect(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            self._display_rect = _DisplayRect(0, 0, self.width(), self.height())
            return
        scaled = self._pixmap.size()
        aspect_mode = None
        qt_obj = QtCore.Qt
        if hasattr(qt_obj, "KeepAspectRatio"):
            aspect_mode = qt_obj.KeepAspectRatio
        elif hasattr(qt_obj, "AspectRatioMode"):
            aspect_mode = getattr(qt_obj.AspectRatioMode, "KeepAspectRatio", None)
        scaled.scale(self.size(), aspect_mode)
        scaled_width = int(scaled.width())
        scaled_height = int(scaled.height())
        x = max(0, (self.width() - scaled_width) // 2)
        y = max(0, (self.height() - scaled_height) // 2)
        self._display_rect = _DisplayRect(x, y, scaled_width, scaled_height)

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
                display_x=float(self._display_rect.x),
                display_y=float(self._display_rect.y),
                display_width=float(self._display_rect.width),
                display_height=float(self._display_rect.height),
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
            display_x=float(self._display_rect.x),
            display_y=float(self._display_rect.y),
            display_width=float(max(1, self._display_rect.width)),
            display_height=float(max(1, self._display_rect.height)),
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
        cast(Any, super()).closeEvent(event)
