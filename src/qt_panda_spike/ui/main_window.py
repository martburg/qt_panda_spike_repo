# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportCallIssue=false
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PySide6 import QtWidgets

from .viewport_widget import ViewportWidget


class MainWindow(QtWidgets.QMainWindow):
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
        self.setWindowTitle(f"qt_panda_spike — {backend_name}")

        root = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        info_fragments = [
            "Native Panda viewport focus: resize, orbit, zoom, and right-click picking against simple pickable nodes.",
            "Left-drag = orbit, wheel = zoom, right-click = pick.",
        ]
        if backend_name != "native":
            info_fragments.append("Offscreen remains available only as a comparison path.")
        if show_dome:
            info_fragments.append("Debug dome is enabled.")
        if pick_debug:
            info_fragments.append(f"Pick diagnostics are appended to: {Path(pick_log_path)}")
        else:
            info_fragments.append("Pick diagnostics and hit markers are disabled.")

        info = QtWidgets.QLabel(" ".join(info_fragments), root)
        cast(Any, info).setWordWrap(True)
        layout.addWidget(info)

        self.viewport = ViewportWidget(
            backend_name=backend_name,
            pick_log_path=pick_log_path,
            pick_debug=pick_debug,
            show_dome=show_dome,
            parent=root,
        )
        self.viewport.picked.connect(self._on_picked)
        layout.addWidget(self.viewport, 1)

        self.status_label = QtWidgets.QLabel("", root)
        cast(Any, self.status_label).setWordWrap(True)
        if pick_debug:
            self.status_label.setText(
                f"Pick: waiting for viewport | debug log: {Path(pick_log_path)}"
            )
        else:
            self.status_label.setText("Pick: waiting for viewport")
        layout.addWidget(self.status_label)

        self.setCentralWidget(root)

    def _on_picked(self, text: str) -> None:
        self.status_label.setText(text)
