from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import QPushButton, QWidget


@dataclass
class YellowBindings:
    """Small, explicit binding layer for the widgets we *actually* use first.

    Expand this gradually (don't try to bind the whole monster UI up-front).
    """

    btn_setup_toggle: QPushButton
    frame_setup: QWidget

    # E-Stop (IP + CFC use these)
    btn_estop_all_set: Optional[QPushButton]
    btn_estop_all_clear: Optional[QPushButton]

    @classmethod
    def from_window(cls, win: QWidget) -> "YellowBindings":
        btn_setup_toggle = win.findChild(QPushButton, "btnSetupToggle")
        frame_setup = win.findChild(QWidget, "frameSetup")
        if btn_setup_toggle is None or frame_setup is None:
            raise RuntimeError("yellow UI missing btnSetupToggle/frameSetup")

        return cls(
            btn_setup_toggle=btn_setup_toggle,
            frame_setup=frame_setup,
            btn_estop_all_set=win.findChild(QPushButton, "btnEStopAllSet"),
            btn_estop_all_clear=win.findChild(QPushButton, "btnEStopAllClear"),
        )
