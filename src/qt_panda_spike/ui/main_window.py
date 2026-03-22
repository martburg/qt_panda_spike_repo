from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QVBoxLayout, QWidget

from .viewport_widget import ViewportWidget


class MainWindow(QMainWindow):
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

        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        info_fragments = ["Left-drag = orbit, wheel = zoom, right-click = pick."]
        if show_dome:
            info_fragments.append("Debug dome is enabled.")
        if pick_debug:
            info_fragments.append(f"Pick diagnostics are appended to: {Path(pick_log_path)}")
        else:
            info_fragments.append("Pick diagnostics and hit markers are disabled.")

        info = QLabel(" ".join(info_fragments), root)
        info.setWordWrap(True)
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
        self.setCentralWidget(root)

        status = QStatusBar(self)
        if pick_debug:
            status.showMessage(f"Pick: waiting for viewport | debug log: {Path(pick_log_path)}")
        else:
            status.showMessage("Pick: waiting for viewport")
        self.setStatusBar(status)

    def _on_picked(self, text: str) -> None:
        self.statusBar().showMessage(text)
