from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from steuerung3d.rig.scene.two_axis_head_snapshot import SceneSnapshot


class ViewportHost(QWidget):
    """Qt-facing viewport contract stub.

    This host intentionally contains no Panda3D logic yet. It gives the shell a
    stable center widget, accepts scene snapshots, and exposes the signals that
    the later native Panda implementation will satisfy.
    """

    selection_changed = Signal(object)
    scene_object_selected = Signal(str)
    viewport_ready = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene: SceneSnapshot | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title_label = QLabel("3D Viewport", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.title_label)

        self.viewport_frame = QFrame(self)
        self.viewport_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.viewport_frame.setMinimumHeight(220)
        self.viewport_frame.setStyleSheet(
            "QFrame { background-color: #161a20; border: 1px solid #404650; }"
        )
        frame_layout = QVBoxLayout(self.viewport_frame)
        frame_layout.setContentsMargins(12, 10, 12, 10)
        frame_layout.setSpacing(6)

        self.viewport_status_label = QLabel("", self.viewport_frame)
        cast(Any, self.viewport_status_label).setWordWrap(True)
        self.viewport_status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.viewport_status_label.setStyleSheet("QLabel { color: #d9dde3; }")
        frame_layout.addWidget(self.viewport_status_label, 1)

        self.viewport_hint_label = QLabel("", self.viewport_frame)
        cast(Any, self.viewport_hint_label).setWordWrap(True)
        self.viewport_hint_label.setStyleSheet("QLabel { color: #96a0ad; font-size: 11px; }")
        frame_layout.addWidget(self.viewport_hint_label)

        layout.addWidget(self.viewport_frame, 1)
        self._refresh_labels()
        self.viewport_ready.emit()

    def apply_scene_snapshot(self, scene: SceneSnapshot | None) -> None:
        self._scene = scene
        self._refresh_labels()

    def viewport_status_text(self) -> str:
        return self.viewport_status_label.text()

    def _refresh_labels(self) -> None:
        scene = self._scene
        if scene is None:
            state_text = "Viewport placeholder. Waiting for supervisor/kinematics scene snapshot."
        else:
            frame_names = ", ".join(frame.name for frame in scene.frames) or "-"
            line_names = ", ".join(line.name for line in scene.lines) or "-"
            debug_line_names = ", ".join(line.name for line in scene.debug_lines) or "-"
            warnings = ", ".join(scene.warnings) or "none"
            state_text = (
                f"machine={scene.machine_id}\n"
                f"frames={len(scene.frames)} [{frame_names}]\n"
                f"lines={len(scene.lines)} [{line_names}]\n"
                f"debug_lines={len(scene.debug_lines)} [{debug_line_names}]\n"
                f"warnings={warnings}"
            )
        self.viewport_status_label.setText(state_text)
        self.viewport_hint_label.setText(
            "Panda hook point prepared. Native Panda backend and floating overlay are not "
            "enabled in this slice yet."
        )
