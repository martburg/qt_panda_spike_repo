# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportCallIssue=false
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from qt_panda_spike.ui.viewport_widget import ViewportWidget

_app = QApplication.instance() or QApplication([])


def test_native_viewport_emits_status() -> None:
    widget = ViewportWidget("native", Path("pick.jsonl"))
    seen: list[str] = []
    widget.picked.connect(seen.append)

    widget._emit_status("Pick: hello native viewport")

    assert seen == ["Pick: hello native viewport"]
    if hasattr(widget, "_overlay_value"):
        assert "Pick: hello native viewport" in widget._overlay_value.text()

    widget.close()


def test_offscreen_viewport_emits_status() -> None:
    widget = ViewportWidget("offscreen", Path("pick.jsonl"))
    seen: list[str] = []
    widget.picked.connect(seen.append)

    widget._emit_status("Pick: hello offscreen viewport")

    assert seen == ["Pick: hello offscreen viewport"]
    if hasattr(widget, "_overlay_value"):
        assert "Pick: hello offscreen viewport" in widget._overlay_value.text()

    widget.close()
