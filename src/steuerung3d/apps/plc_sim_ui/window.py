"""PLC sim UI (Qt) main window.

This module contains the heavy Qt widget layout. It is split out of
``__main__.py`` so the entrypoint stays small and importable.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from .widgets import LedColors, LedIndicator, hline, make_edit, make_readout, make_small_readonly


@dataclass
class _AxisPanelRefs:
    # A tiny structure to keep the original file's attribute usage intact.
    txt_name: QLineEdit


class YellowAxisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Achsen Steuerung")
        self.setMinimumSize(742, 428)

        root = QWidget()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        header = self._build_header()
        outer.addWidget(header)

        mid = QHBoxLayout()
        mid.setSpacing(6)

        left = self._build_estop_column()
        mid.addWidget(left)

        main = self._build_main_panels()
        mid.addWidget(main, 1)

        outer.addLayout(mid, 1)

        bottom = self._build_bottom_strip()
        outer.addWidget(bottom)

        apply_darkish_style(self)

    # ----------------
    # Builders
    # ----------------

    def _build_header(self) -> QWidget:
        box = QGroupBox()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(10, 6, 10, 6)

        lbl = QLabel("Achse")
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        lay.addWidget(lbl)

        self.cmb_axis = QComboBox()
        self.cmb_axis.addItems(["Anton", "Berta", "Caesar", "Dora"])
        self.cmb_axis.setFixedWidth(130)
        lay.addWidget(self.cmb_axis)

        lay.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.txt_time = QLineEdit("00:00:00")
        self.txt_time.setReadOnly(True)
        self.txt_time.setAlignment(Qt.AlignCenter)
        self.txt_time.setFixedWidth(90)
        lay.addWidget(self.txt_time)

        return box

    def _build_estop_column(self) -> QWidget:
        box = QGroupBox("Nothalt")
        box.setFixedWidth(210)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.btn_estop_reset = QPushButton("E-Stop Reset")
        self.btn_estop_reset.setObjectName("btnEStopReset")
        lay.addWidget(self.btn_estop_reset)

        lay.addWidget(hline())

        self.led_estop = LedIndicator("E-Stop", LedColors(on=QColor(200, 0, 0)), checked=True)
        self.led_fault = LedIndicator("Fault", LedColors(on=QColor(200, 120, 0)), checked=False)
        self.led_online = LedIndicator("Online", LedColors(on=QColor(0, 200, 0)), checked=True)

        lay.addWidget(self.led_estop)
        lay.addWidget(self.led_fault)
        lay.addWidget(self.led_online)

        lay.addItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))
        return box

    def _build_main_panels(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        lay.addWidget(self._build_left_panel())
        lay.addWidget(self._build_right_panel())
        return w

    def _build_left_panel(self) -> QWidget:
        box = QGroupBox("Soll / Ist")
        lay = QGridLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(6)

        # Row 0
        lay.addWidget(QLabel("Speed Soll"), 0, 0)
        self.txt_speed_soll = make_readout()
        lay.addWidget(self.txt_speed_soll, 0, 1)
        lay.addWidget(QLabel("m/s"), 0, 2)

        # Row 1
        lay.addWidget(QLabel("Speed Ist"), 1, 0)
        self.txt_speed_ist = make_readout()
        lay.addWidget(self.txt_speed_ist, 1, 1)
        lay.addWidget(QLabel("m/s"), 1, 2)

        # Row 2
        lay.addWidget(QLabel("Pos Soll"), 2, 0)
        self.txt_pos_soll = make_readout(width=110)
        lay.addWidget(self.txt_pos_soll, 2, 1)
        lay.addWidget(QLabel("m"), 2, 2)

        # Row 3
        lay.addWidget(QLabel("Pos Ist"), 3, 0)
        self.txt_pos_ist = make_readout(width=110)
        lay.addWidget(self.txt_pos_ist, 3, 1)
        lay.addWidget(QLabel("m"), 3, 2)

        # Row 4
        lay.addWidget(QLabel("Lag Error"), 4, 0)
        self.txt_lag_error = make_readout(width=110)
        self.txt_lag_error.setObjectName("txtLagError")
        lay.addWidget(self.txt_lag_error, 4, 1)
        lay.addWidget(QLabel("m"), 4, 2)

        # Row 5
        lay.addWidget(QLabel("VelMaxMot"), 5, 0)
        self.txt_velmax = make_readout(width=110)
        self.txt_velmax.setObjectName("txtVelMaxMot")
        lay.addWidget(self.txt_velmax, 5, 1)
        lay.addWidget(QLabel("m/s"), 5, 2)

        return box

    def _build_right_panel(self) -> QWidget:
        box = QGroupBox("Steuerung")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # Enable + Motion
        top = QGroupBox("Enable")
        gl = QGridLayout(top)
        gl.setContentsMargins(8, 8, 8, 8)
        gl.setHorizontalSpacing(8)
        gl.setVerticalSpacing(6)

        self.led_enable = LedIndicator("Enable", LedColors(on=QColor(0, 200, 0)), checked=False)
        self.led_motion = LedIndicator("Motion", LedColors(on=QColor(0, 200, 0)), checked=False)
        gl.addWidget(self.led_enable, 0, 0)
        gl.addWidget(self.led_motion, 1, 0)

        self.btn_enable = QPushButton("Enable")
        self.btn_disable = QPushButton("Disable")
        gl.addWidget(self.btn_enable, 0, 1)
        gl.addWidget(self.btn_disable, 1, 1)

        lay.addWidget(top)

        # Slider panel
        sp = QGroupBox("Soll Speed")
        spl = QHBoxLayout(sp)
        spl.setContentsMargins(8, 8, 8, 8)
        self.sld_speed = QSlider(Qt.Vertical)
        self.sld_speed.setRange(-100, 100)
        self.sld_speed.setValue(0)
        self.txt_speed_cmd = make_small_readonly(width=90)
        spl.addWidget(self.sld_speed)
        spl.addWidget(self.txt_speed_cmd)
        lay.addWidget(sp, 1)

        # Params panel
        pp = QGroupBox("Params")
        pgl = QGridLayout(pp)
        pgl.setContentsMargins(8, 8, 8, 8)
        pgl.setHorizontalSpacing(8)
        pgl.setVerticalSpacing(6)

        pgl.addWidget(QLabel("OwnPID"), 0, 0)
        self.txt_ownpid = make_edit(70, "1234")
        pgl.addWidget(self.txt_ownpid, 0, 1)

        pgl.addWidget(QLabel("ControlPID"), 1, 0)
        self.txt_controlpid = make_edit(70, "0")
        pgl.addWidget(self.txt_controlpid, 1, 1)

        pgl.addWidget(QLabel("Modus"), 2, 0)
        self.txt_modus = make_edit(70, "E")
        pgl.addWidget(self.txt_modus, 2, 1)

        lay.addWidget(pp)

        return box

    def _build_bottom_strip(self) -> QWidget:
        box = QGroupBox()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        lay.addWidget(QLabel("Debug:"))
        self.txt_dbg = QLineEdit("-")
        self.txt_dbg.setReadOnly(True)
        lay.addWidget(self.txt_dbg, 1)
        return box


def apply_darkish_style(root: QWidget) -> None:
    root.setStyleSheet(
        """
        QWidget { background: #2b2b2b; color: #eaeaea; }
        QGroupBox {
            border: 1px solid #555;
            border-radius: 8px;
            margin-top: 8px;
            padding: 6px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px 0 4px;
        }
        QLabel { color: #eaeaea; }

        QLineEdit {
            background: #efefef;
            border: 1px solid #666;
            border-radius: 4px;
            padding: 2px 6px;
            color: #111;
        }
        QLineEdit#txtVelMaxMot { color: #c00000; font-weight: bold; }
        QLineEdit#txtLagError { color: #c00000; font-weight: bold; }

        QPushButton {
            background: #efefef;
            border: 1px solid #555;
            border-radius: 6px;
            padding: 5px 10px;
        }
        QPushButton:pressed { background: #dcdcdc; }
        QPushButton#btnEStopReset {
            background: #efefef;
            font-weight: bold;
            padding: 8px;
        }

        QComboBox {
            background: #efefef;
            border: 1px solid #666;
            border-radius: 6px;
            padding: 4px 8px;
        }

        QSlider::groove:vertical {
            background: rgba(255,255,255,0.25);
            width: 10px;
            border-radius: 5px;
        }
        QSlider::handle:vertical {
            background: #efefef;
            height: 14px;
            margin: -2px;
            border: 1px solid #555;
            border-radius: 7px;
        }
        """
    )


def main(argv: list[str] | None = None) -> int:
    app = QApplication(list(sys.argv if argv is None else argv))

    f = QFont()
    f.setPointSize(9)
    app.setFont(f)

    w = YellowAxisWindow()
    w.show()
    return app.exec()
