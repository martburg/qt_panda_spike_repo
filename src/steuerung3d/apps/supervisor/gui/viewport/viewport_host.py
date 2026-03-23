from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from steuerung3d.rig.scene.two_axis_head_snapshot import SceneSnapshot

from .panda_backend import PandaViewportBackend
from .selection_bridge import selection_event_from_pick_result, selection_summary_from_event


class ViewportHost(QWidget):
    """Qt-facing viewport host using a native Panda child window.

    The public contract intentionally matches the earlier placeholder host so the
    rest of the supervisor shell stays unchanged.
    """

    selection_changed = Signal(object)
    scene_object_selected = Signal(str)
    viewport_ready = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene: SceneSnapshot | None = None
        self._backend = PandaViewportBackend()
        self._backend_started = False
        self._backend_failed = False
        self._selected_summary_text = "No viewport selection"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title_label = QLabel("3D Viewport", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.title_label)

        self.viewport_container = QFrame(self)
        self.viewport_container.setFrameShape(QFrame.Shape.StyledPanel)
        self.viewport_container.setMinimumHeight(260)
        self.viewport_container.setStyleSheet(
            "QFrame { background-color: #161a20; border: 1px solid #404650; }"
        )
        container_layout = QVBoxLayout(self.viewport_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.viewport_frame = QWidget(self.viewport_container)
        self.viewport_frame.setMinimumHeight(260)
        self.viewport_frame.setStyleSheet("")
        widget_attributes = cast(Any, Qt.WidgetAttribute)
        native_window_attr = widget_attributes.WA_NativeWindow
        dont_create_ancestors_attr = widget_attributes.WA_DontCreateNativeAncestors
        cast(Any, self.viewport_frame).setAttribute(native_window_attr, True)
        cast(Any, self.viewport_frame).setAttribute(dont_create_ancestors_attr, True)
        cast(Any, self.viewport_frame).setAutoFillBackground(False)
        container_layout.addWidget(self.viewport_frame, 1)
        layout.addWidget(self.viewport_container, 1)

        self.viewport_status_label = QLabel("", self)
        cast(Any, self.viewport_status_label).setWordWrap(True)
        self.viewport_status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.viewport_status_label.setStyleSheet("QLabel { color: #d9dde3; }")
        layout.addWidget(self.viewport_status_label)

        self.viewport_hint_label = QLabel("", self)
        cast(Any, self.viewport_hint_label).setWordWrap(True)
        self.viewport_hint_label.setStyleSheet("QLabel { color: #96a0ad; font-size: 11px; }")
        layout.addWidget(self.viewport_hint_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        self._resize_timer = QTimer(self)
        cast(Any, self._resize_timer).setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_deferred_resize)

        self._refresh_labels()
        self.viewport_ready.emit()

    def showEvent(self, event: Any) -> None:
        cast(Any, super()).showEvent(event)
        self._ensure_backend_started()
        self._schedule_resize()

    def resizeEvent(self, event: Any) -> None:
        cast(Any, super()).resizeEvent(event)
        self._schedule_resize()

    def closeEvent(self, event: Any) -> None:
        self._timer.stop()
        self._resize_timer.stop()
        self._backend.shutdown()
        self._backend_started = False
        cast(Any, super()).closeEvent(event)

    def apply_scene_snapshot(self, scene: SceneSnapshot | None) -> None:
        self._scene = scene
        if self._backend_started:
            self._backend.apply_scene_snapshot(scene)
        self._refresh_labels()

    def viewport_status_text(self) -> str:
        return self.viewport_status_label.text()

    def _ensure_backend_started(self) -> None:
        if self._backend_started or self._backend_failed:
            return
        try:
            self._backend.start(self.viewport_frame)
            self._backend_started = True
            if self._scene is not None:
                self._backend.apply_scene_snapshot(self._scene)
        except Exception as exc:
            self._backend_failed = True
            self.viewport_status_label.setText(f"Native Panda backend failed to start: {exc}")
            self.viewport_hint_label.setText(
                "Fallback active. Check Panda3D availability and native child-window support."
            )

    def _schedule_resize(self) -> None:
        if not self.isVisible():
            return
        self._resize_timer.start(40)

    def _apply_deferred_resize(self) -> None:
        if not self.isVisible():
            return
        self._ensure_backend_started()
        if self._backend_started:
            self._backend.resize(
                int(self.viewport_frame.width()), int(self.viewport_frame.height())
            )

    def _tick(self) -> None:
        if not self.isVisible():
            return
        self._ensure_backend_started()
        if not self._backend_started:
            return
        self._backend.step()
        for pick in self._backend.drain_pick_results():
            event = selection_event_from_pick_result(pick)
            summary = selection_summary_from_event(event)
            self._selected_summary_text = summary.summary_text
            if event is not None:
                self.selection_changed.emit(event)
                self.scene_object_selected.emit(event.object_name)
        messages = self._backend.drain_status_messages()
        if messages:
            self.viewport_status_label.setText(messages[-1])
            self._refresh_labels(status_override=messages[-1])

    def _refresh_labels(self, status_override: str | None = None) -> None:
        scene = self._scene
        if status_override is None:
            if scene is None:
                status_text = "Native Panda demo scene active. Waiting for supervisor/kinematic scene snapshot."
            else:
                status_text = (
                    f"Native Panda demo scene active. scene frames={len(scene.frames)} "
                    f"lines={len(scene.lines)}"
                )
        else:
            status_text = status_override

        self.viewport_status_label.setText(status_text)
        hint_lines = [
            "Left-drag = orbit | mouse wheel = zoom | right-click = pick.",
            f"Selection: {self._selected_summary_text}",
        ]
        if scene is None:
            hint_lines.append(
                "Demo nodes remain visible until a real Panda scene adapter is added."
            )
        else:
            hint_lines.append(
                "Scene snapshot is connected; this slice still renders generic demo nodes."
            )
        self.viewport_hint_label.setText("\n".join(hint_lines))
