from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from qt_panda_spike.ui.viewport_widget import ViewportWidget


_app = QApplication.instance() or QApplication([])


def test_native_overlay_uses_floating_frameless_window() -> None:
    widget = ViewportWidget("native", Path("pick.jsonl"))
    widget.resize(640, 360)

    assert widget._overlay_label.text() == "Overlay"
    assert "backend=native" in widget._overlay_value.text()
    assert widget._overlay_panel.isHidden() is True
    assert widget._floating_overlay is not None
    assert widget._floating_overlay.label.text() == "Overlay"
    assert "backend=native" in widget._floating_overlay.value.text()
    flags = widget._floating_overlay.windowFlags()
    assert bool(flags & Qt.WindowType.Tool)
    assert bool(flags & Qt.WindowType.FramelessWindowHint)

    widget.close()


def test_offscreen_overlay_tracks_status_messages() -> None:
    widget = ViewportWidget("offscreen", Path("pick.jsonl"))
    seen: list[str] = []
    widget.picked.connect(seen.append)

    widget._emit_status("Pick: hello overlay")

    assert widget._overlay_value.text() == "Pick: hello overlay"
    assert seen == ["Pick: hello overlay"]
    assert widget._overlay_panel.isHidden() is False
    assert widget._floating_overlay is None

    widget.close()
