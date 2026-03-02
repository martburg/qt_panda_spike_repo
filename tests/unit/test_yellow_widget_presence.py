from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from steuerung3d.apps.yellow import ui_shell


def _ensure_app() -> None:
    if QApplication.instance() is not None:
        return
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication([])


@pytest.mark.ui
def test_yellow_ui_widget_presence() -> None:
    _ensure_app()
    root = Path(__file__).resolve().parents[2]
    ui_path = root / "src" / "steuerung3d" / "apps" / "yellow" / "assets" / "yellow3_merged.ui"
    win = ui_shell.load_ui(ui_path)

    required = [
        "cmbAxis",
        "txtTick",
        "txtHdrBannerLeft",
        "txtHdrBannerRight",
        "txtGuiderSpeed",
        "btnEStopReset",
        "btnDiagResync",
    ]
    for name in required:
        w = win.findChild(QWidget, name)
        assert w is not None, f"Missing widget: {name}"
