# src/steuerung3d/apps/yellow/controllers/bindings.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import QPushButton, QWidget, QFrame


@dataclass
class YellowBindings:
    btn_setup_toggle: QPushButton
    frame_setup: QWidget

    # E-Stop (CFC diagnostics)
    btn_estop_all_set: Optional[QPushButton]
    btn_estop_all_clear: Optional[QPushButton]

    # E-Stop reset (IP)
    btn_estop_reset: Optional[QPushButton]

    # E-Stop status dots (both roles render these)
    dot_master: Optional[QFrame]
    dot_guider: Optional[QFrame]
    dot_network: Optional[QFrame]
    dot_estop1: Optional[QFrame]
    dot_estop2: Optional[QFrame]

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
            btn_estop_reset=win.findChild(QPushButton, "btnEStopReset"),
            dot_master=win.findChild(QFrame, "dotMaster"),
            dot_guider=win.findChild(QFrame, "dotGuider"),
            dot_network=win.findChild(QFrame, "dotNetwork"),
            dot_estop1=win.findChild(QFrame, "dotEStop1"),
            dot_estop2=win.findChild(QFrame, "dotEStop2"),
        )
