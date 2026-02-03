# __main__.py
# PySide6 "Yellow Axis UI" layout shell (no backend logic)
#
# Drop this file into:  src/steuerung3d/apps/yellow_axis_ui_qt/__main__.py
# Then run:
#   python -m steuerung3d.apps.yellow_axis_ui_qt
#
# Or run directly (from its folder):
#   python __main__.py

from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpacerItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QMainWindow,
)


# -----------------------------
# Small UI primitives
# -----------------------------

@dataclass
class LedColors:
    on: QColor
    off: QColor = QColor(70, 70, 70)
    ring: QColor = QColor(30, 30, 30)


class LedIndicator(QWidget):
    """Round LED + label, purely visual."""
    def __init__(self, text: str, colors: LedColors, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self._text = text
        self._colors = colors
        self._checked = checked
        self.setMinimumHeight(18)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(90, 18)

    def setChecked(self, v: bool) -> None:
        if self._checked != v:
            self._checked = v
            self.update()

    def isChecked(self) -> bool:
        return self._checked

    def paintEvent(self, _evt) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # LED circle
        h = self.height()
        r = min(12, h - 4)
        cx = 10
        cy = h // 2

        fill = self._colors.on if self._checked else self._colors.off
        p.setPen(QPen(self._colors.ring, 1))
        p.setBrush(fill)
        p.drawEllipse(cx - r // 2, cy - r // 2, r, r)

        # Label
        p.setPen(QPen(QColor(230, 230, 230), 1))
        font = p.font()
        font.setPointSize(9)
        p.setFont(font)
        p.drawText(22, 0, self.width() - 22, h, Qt.AlignVCenter | Qt.AlignLeft, self._text)


def make_readout(width: int = 90, bold: bool = True) -> QLineEdit:
    e = QLineEdit("99.99")
    e.setReadOnly(True)
    e.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    f = e.font()
    f.setPointSize(11)
    f.setBold(bold)
    e.setFont(f)
    e.setFixedWidth(width)
    return e


def make_small_readonly(width: int = 80) -> QLineEdit:
    e = QLineEdit("0")
    e.setReadOnly(True)
    e.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    e.setFixedWidth(width)
    return e


def make_edit(width: int = 80, text: str = "0") -> QLineEdit:
    e = QLineEdit(text)
    e.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    e.setFixedWidth(width)
    return e


def hline() -> QFrame:
    ln = QFrame()
    ln.setFrameShape(QFrame.HLine)
    ln.setFrameShadow(QFrame.Sunken)
    return ln


# -----------------------------
# Main Window
# -----------------------------

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

        # Header
        header = self._build_header()
        outer.addWidget(header)

        # Middle: Left E-Stop/status column + Main panels
        mid = QHBoxLayout()
        mid.setSpacing(6)

        left = self._build_estop_column()
        mid.addWidget(left)

        main = self._build_main_panels()
        mid.addWidget(main, 1)

        outer.addLayout(mid, 1)

        # Bottom strip
        bottom = self._build_bottom_strip()
        outer.addWidget(bottom)

        self._apply_qss()

    # -------- UI blocks --------

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("frameHeader")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)

        # Axis selector + "Engine" line
        left = QVBoxLayout()
        left.setSpacing(4)

        self.cmb_axis = QComboBox()
        self.cmb_axis.addItems(["Anton", "Debby", "Burt", "Cecil", "SIMUL"])
        self.cmb_axis.setEditable(False)
        self.cmb_axis.setFixedWidth(220)

        lbl_engine = QLabel("Engine")
        lbl_engine.setObjectName("lblHeaderSmall")

        left.addWidget(self.cmb_axis)
        left.addWidget(lbl_engine)
        lay.addLayout(left)

        # Big readouts
        self.txt_pos = make_readout(105)
        self.txt_vel = make_readout(105)
        self.txt_amp = make_readout(105)
        lay.addWidget(self._wrap_with_unit(self.txt_pos, "m"))
        lay.addWidget(self._wrap_with_unit(self.txt_vel, "m/s"))
        lay.addWidget(self._wrap_with_unit(self.txt_amp, "A"))

        # Big vertical slider
        self.sld_vel = QSlider(Qt.Vertical)
        self.sld_vel.setRange(0, 1000)
        self.sld_vel.setValue(500)
        self.sld_vel.setFixedHeight(70)
        self.sld_vel.setFixedWidth(26)
        lay.addWidget(self.sld_vel)

        # LED row (FBT, Ready, Online, Brake1, Brake2)
        leds = QVBoxLayout()
        leds.setSpacing(4)
        self.led_fbt = LedIndicator("FBT", LedColors(on=QColor(250, 198, 12)), checked=False)
        self.led_ready = LedIndicator("Ready", LedColors(on=QColor(0, 170, 0)), checked=True)
        self.led_online = LedIndicator("Online", LedColors(on=QColor(0, 170, 0)), checked=True)
        self.led_brk1 = LedIndicator("Brake 1", LedColors(on=QColor(0, 170, 0)), checked=True)
        self.led_brk2 = LedIndicator("Brake 2", LedColors(on=QColor(0, 170, 0)), checked=True)
        leds.addWidget(self.led_fbt)
        leds.addWidget(self.led_ready)
        leds.addWidget(self.led_online)
        leds.addWidget(self.led_brk1)
        leds.addWidget(self.led_brk2)
        lay.addLayout(leds)

        # Right actions/temps
        right = QVBoxLayout()
        right.setSpacing(4)

        # Status display (legacy name was txt_status; clarify meaning)
        self.txt_main_amp_status = QLineEdit("F 999/99")
        self.txt_main_amp_status.setReadOnly(True)
        self.txt_main_amp_status.setAlignment(Qt.AlignCenter)
        self.txt_main_amp_status.setFixedWidth(110)

        btn_reset = QPushButton("Reset")
        btn_reset.setFixedWidth(110)

        temp_row = QHBoxLayout()
        self.txt_temp = QLineEdit("99 C")
        self.txt_temp.setReadOnly(True)
        self.txt_temp.setAlignment(Qt.AlignCenter)
        self.txt_temp.setFixedWidth(70)
        self.txt_tick = QLineEdit("99")
        self.txt_tick.setReadOnly(True)
        self.txt_tick.setAlignment(Qt.AlignCenter)
        self.txt_tick.setFixedWidth(32)
        temp_row.addWidget(self.txt_temp)
        temp_row.addWidget(self.txt_tick)

        right.addWidget(self.txt_main_amp_status)
        right.addWidget(btn_reset)
        right.addLayout(temp_row)
        right.addItem(QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding))

        lay.addLayout(right)

        return frame

    def _wrap_with_unit(self, edit: QLineEdit, unit: str) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.addWidget(edit)
        u = QLabel(unit)
        u.setObjectName("lblUnit")
        h.addWidget(u)
        return w

    def _build_estop_column(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("frameEStop")
        frame.setFixedWidth(200)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # Top: Master/Guider/Network + RESET
        top = QGroupBox("")
        top.setObjectName("gbEStopSection")
        tl = QVBoxLayout(top)
        tl.setContentsMargins(8, 6, 8, 6)
        tl.setSpacing(6)

        self.es_master = LedIndicator("Master", LedColors(on=QColor(50, 150, 255)), checked=True)
        self.es_guider = LedIndicator("Guider", LedColors(on=QColor(50, 150, 255)), checked=True)
        self.es_network = LedIndicator("Network", LedColors(on=QColor(50, 150, 255)), checked=True)
        btn_es_reset = QPushButton("RESET")
        btn_es_reset.setObjectName("btnEStopReset")

        tl.addWidget(self.es_master)
        tl.addWidget(self.es_guider)
        tl.addWidget(self.es_network)
        tl.addWidget(btn_es_reset)
        lay.addWidget(top)

        # Middle: E-Stop + power/brake/sps/etc.
        mid = QGroupBox("")
        mid.setObjectName("gbEStopSection")
        ml = QGridLayout(mid)
        ml.setContentsMargins(8, 6, 8, 6)
        ml.setHorizontalSpacing(10)
        ml.setVerticalSpacing(6)

        def add_led(r: int, c: int, text: str, checked: bool = True):
            led = LedIndicator(text, LedColors(on=QColor(50, 150, 255)), checked=checked)
            ml.addWidget(led, r, c)
            return led

        self.es_estop1 = add_led(0, 0, "E-Stop 1", True)
        self.es_30kw = add_led(0, 1, "30kW OK", True)
        self.es_estop2 = add_led(1, 0, "E-Stop 2", True)
        self.es_05kw = add_led(1, 1, "05kW OK", True)

        self.es_brk1 = add_led(2, 0, "BRK 1 OK", True)
        self.es_brk2 = add_led(2, 1, "BRK 2 OK", True)
        self.es_brk2kb = add_led(3, 1, "BRK 2 KB", True)

        self.es_sps = add_led(3, 0, "SPS OK", True)
        self.es_red = add_led(4, 0, "Red OK", True)
        self.es_enc = add_led(4, 1, "ENC OK", True)

        self.es_poswin = add_led(5, 0, "Pos Win", True)
        self.es_velwin = add_led(5, 1, "Vel Win", True)
        self.es_endlage = add_led(6, 0, "Endlage", True)

        lay.addWidget(mid)

        # Bottom: G1/G2/G3 COM/FB/OUT blocks
        g = QGroupBox("")
        g.setObjectName("gbEStopSection")
        gl = QGridLayout(g)
        gl.setContentsMargins(8, 6, 8, 6)
        gl.setHorizontalSpacing(8)
        gl.setVerticalSpacing(6)

        headers = ["COM", "FB", "OUT"]
        for i, h in enumerate(headers):
            lab = QLabel(h)
            lab.setObjectName("lblHeaderSmall")
            lab.setAlignment(Qt.AlignCenter)
            gl.addWidget(lab, 0, i + 1)

        def add_row(row: int, name: str):
            gl.addWidget(QLabel(name), row, 0)
            gl.addWidget(LedIndicator("", LedColors(on=QColor(50, 150, 255)), checked=True), row, 1)
            gl.addWidget(LedIndicator("", LedColors(on=QColor(50, 150, 255)), checked=True), row, 2)
            gl.addWidget(LedIndicator("", LedColors(on=QColor(50, 150, 255)), checked=True), row, 3)

        add_row(1, "G1")
        add_row(2, "G2")
        add_row(3, "G3")

        lay.addWidget(g)
        lay.addItem(QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding))

        return frame

    def _build_main_panels(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("frameMain")

        grid = QGridLayout(frame)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        gb_positions = self._gb_positions()
        gb_vel = self._gb_vel_acc_amp()
        gb_guider = self._gb_guider()
        gb_filter = self._gb_filter()
        gb_rope = self._gb_rope()

        # Rough placement as per screenshot
        grid.addWidget(gb_positions, 0, 0)
        grid.addWidget(gb_vel, 0, 1)
        grid.addWidget(gb_guider, 1, 0)
        grid.addWidget(gb_filter, 1, 1)
        grid.addWidget(gb_rope, 1, 2)

        # allow main cells to expand
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 1)

        return frame

    def _gb_positions(self) -> QGroupBox:
        gb = QGroupBox("Positions")
        gb.setObjectName("gbPanel")
        gl = QGridLayout(gb)

        btn_edit = QPushButton("Edit")
        btn_write = QPushButton("Write")
        btn_cancel = QPushButton("Cancel")

        labels = ["Hard Max", "User Max", "Act Pos", "User Min", "Hard Min", "Pos Win"]
        values = ["300.0", "300.0", "0", "-10.0", "-10.0", "0.01"]

        for i, (lab, val) in enumerate(zip(labels, values)):
            gl.addWidget(QLabel(lab), i, 0)
            if lab == "Act Pos":
                gl.addWidget(make_small_readonly(90), i, 1)
            else:
                gl.addWidget(make_edit(90, val), i, 1)

        gl.addWidget(btn_edit, 0, 2)
        gl.addItem(QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding), 1, 2)
        gl.addWidget(btn_write, 5, 2)
        gl.addWidget(btn_cancel, 6, 2)

        return gb

    def _gb_vel_acc_amp(self) -> QGroupBox:
        gb = QGroupBox("Vel / Acc / Amp")
        gb.setObjectName("gbPanel")
        gl = QGridLayout(gb)

        btn_edit = QPushButton("Edit")
        btn_write = QPushButton("Write")
        btn_cancel = QPushButton("Cancel")

        # include VelMaxMot (red label in screenshot)
        gl.addWidget(QLabel("VelMaxMot"), 0, 0)
        mot = make_small_readonly(90)
        mot.setText("0")
        mot.setObjectName("txtVelMaxMot")
        gl.addWidget(mot, 0, 1)

        rows = [
            ("Vel Max", "6.0"),
            ("Acc Max", "1.5"),
            ("Dcc Max", "1.5"),
            ("Acc Move", "5.00"),
            ("Max Amp", "0"),
            ("Vel Win", "0.01"),
        ]
        for i, (lab, val) in enumerate(rows, start=1):
            gl.addWidget(QLabel(lab), i, 0)
            gl.addWidget(make_edit(90, val), i, 1)

        gl.addWidget(btn_edit, 0, 2)
        gl.addItem(QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding), 2, 2)
        gl.addWidget(btn_write, 6, 2)
        gl.addWidget(btn_cancel, 7, 2)

        return gb

    def _gb_guider(self) -> QGroupBox:
        gb = QGroupBox("Guider")
        gb.setObjectName("gbPanel")
        gl = QGridLayout(gb)

        # top readouts + buttons
        gl.addWidget(QLabel(""), 0, 0)
        gl.addWidget(make_small_readonly(80), 0, 1)  # pos
        gl.addWidget(make_small_readonly(80), 0, 2)  # vel

        btn_engaged = QPushButton("engaged")
        btn_engaged.setCheckable(True)
        btn_engaged.setChecked(True)
        btn_reset = QPushButton("Reset")

        gl.addWidget(btn_engaged, 0, 3)
        gl.addWidget(btn_reset, 1, 3)

        # slider imitation + LEDs
        self.guider_ready = LedIndicator("Ready", LedColors(on=QColor(0, 170, 0)), checked=True)
        self.guider_online = LedIndicator("Online", LedColors(on=QColor(0, 170, 0)), checked=True)

        sld = QSlider(Qt.Vertical)
        sld.setRange(0, 100)
        sld.setValue(50)
        sld.setFixedHeight(80)
        sld.setFixedWidth(26)

        gl.addWidget(self.guider_ready, 1, 0, 1, 2)
        gl.addWidget(self.guider_online, 2, 0, 1, 2)
        gl.addWidget(sld, 1, 2, 2, 1)

        # setup mini box (Pitch/PosMax/PosMin) with edit/write/cancel like screenshot
        sub = QGroupBox("")
        sub.setObjectName("gbPanelSub")
        sl = QGridLayout(sub)
        sl.addWidget(QLabel("Pitch"), 0, 0)
        sl.addWidget(make_edit(80, "6.3"), 0, 1)
        sl.addWidget(QLabel("Pos Max"), 1, 0)
        sl.addWidget(make_edit(80, "0"), 1, 1)
        sl.addWidget(QLabel("Pos Min"), 2, 0)
        sl.addWidget(make_edit(80, "0"), 2, 1)
        sl.addWidget(QPushButton("Edit"), 0, 2)
        sl.addWidget(QPushButton("Write"), 2, 2)
        sl.addWidget(QPushButton("Cancel"), 3, 2)

        gl.addWidget(sub, 3, 0, 1, 4)

        return gb

    def _gb_filter(self) -> QGroupBox:
        gb = QGroupBox("Filter")
        gb.setObjectName("gbPanel")
        gl = QGridLayout(gb)

        btn_edit = QPushButton("Edit")
        btn_write = QPushButton("Write")
        btn_cancel = QPushButton("Cancel")

        gl.addWidget(QLabel("Lag Error"), 0, 0)
        lag = make_small_readonly(90)
        lag.setText("0")
        lag.setObjectName("txtLagError")
        gl.addWidget(lag, 0, 1)
        gl.addWidget(btn_edit, 0, 2)

        rows = [
            ("Prop.", "0"),
            ("Integral", "0"),
            ("Derivate", "0"),
            ("Int. Lim.", "0"),
            ("Rampform", "0"),
        ]
        for i, (lab, val) in enumerate(rows, start=1):
            gl.addWidget(QLabel(lab), i, 0)
            gl.addWidget(make_edit(90, val), i, 1)

        gl.addWidget(btn_write, 6, 2)
        gl.addWidget(btn_cancel, 7, 2)

        return gb

    def _gb_rope(self) -> QGroupBox:
        gb = QGroupBox("Rope")
        gb.setObjectName("gbPanel")
        gl = QGridLayout(gb)

        btn_info = QPushButton("Info Only")
        btn_info.setEnabled(True)

        rows = [
            ("SWLL", "0"),
            ("Diameter", "0"),
            ("Type", "0"),
            ("Number", "0"),
            ("Length", "0"),
        ]
        for i, (lab, val) in enumerate(rows):
            gl.addWidget(QLabel(lab), i, 0)
            gl.addWidget(make_small_readonly(90), i, 1)

        gl.addWidget(btn_info, 0, 2)
        gl.addWidget(QPushButton("Write"), 5, 2)
        gl.addWidget(QPushButton("Cancel"), 6, 2)

        return gb

    def _build_bottom_strip(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("frameBottom")

        lay = QHBoxLayout(frame)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(10)

        # Recover block
        lay.addWidget(QLabel("Recover"))
        self.txt_cut_pos = make_small_readonly(90)
        self.txt_cut_pos.setText("999.99")
        lay.addWidget(self._wrap_label_field("Cut Pos", self.txt_cut_pos))

        self.txt_cut_vel = make_small_readonly(90)
        lay.addWidget(self._wrap_label_field("Cut Vel", self.txt_cut_vel))

        self.txt_cut_time = make_small_readonly(120)
        self.txt_cut_time.setText("14-12-2011 13:36:52 123 ms")
        lay.addWidget(self._wrap_label_field("Cut Time", self.txt_cut_time))

        self.txt_posdiff = make_small_readonly(80)
        self.txt_posdiff.setText("0")
        lay.addWidget(self._wrap_label_field("PosDiff", self.txt_posdiff))

        btn_recover = QPushButton("Recover")
        btn_resync = QPushButton("ReSync")
        lay.addWidget(btn_recover)
        lay.addWidget(btn_resync)

        lay.addItem(QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum))
        return frame

    def _wrap_label_field(self, label: str, field: QLineEdit) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        lab = QLabel(label)
        lab.setObjectName("lblHeaderSmall")
        v.addWidget(lab)
        v.addWidget(field)
        return w

    # -------- Styling --------

    def _apply_qss(self) -> None:
        # Color palette roughly matching your screenshot.
        self.setStyleSheet("""
            QMainWindow { background: #5b0d0d; }
            #frameHeader, #frameBottom { background: #7a1a1a; border: 1px solid #3a0a0a; border-radius: 6px; }
            #frameMain { background: #7a1a1a; border: 1px solid #3a0a0a; border-radius: 6px; }
            #frameEStop { background: #f5c60c; border: 1px solid #7a5d00; border-radius: 6px; }

            QGroupBox#gbPanel {
                background: #d8d8d8;
                border: 1px solid #555;
                border-radius: 6px;
                margin-top: 18px;
                color: #111;
            }
            QGroupBox#gbPanel::title {
                subcontrol-origin: margin;
                left: 10px;
                top: 4px;
                padding: 0 6px;
                color: #111;
                font-weight: bold;
            }

            QGroupBox#gbPanelSub {
                background: #cfcfcf;
                border: 1px solid #666;
                border-radius: 6px;
            }

            QGroupBox#gbEStopSection {
                background: rgba(255,255,255,0.15);
                border: 1px solid rgba(0,0,0,0.25);
                border-radius: 6px;
            }

            QLabel { color: #111; }
            QLabel#lblUnit { color: #eee; font-weight: bold; }
            QLabel#lblHeaderSmall { color: #eee; }

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
        """)


def main() -> int:
    app = QApplication(sys.argv)

    # Slightly more "industrial" default font
    f = QFont()
    f.setPointSize(9)
    app.setFont(f)

    w = YellowAxisWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
