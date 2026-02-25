from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLineEdit, QSizePolicy, QWidget


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

    def sizeHint(self) -> QSize:  # pragma: no cover (Qt)
        return QSize(90, 18)

    def setChecked(self, v: bool) -> None:
        if self._checked != v:
            self._checked = v
            self.update()

    def isChecked(self) -> bool:
        return self._checked

    def paintEvent(self, _evt) -> None:  # pragma: no cover (Qt)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        h = self.height()
        r = min(12, h - 4)
        cx = 10
        cy = h // 2

        fill = self._colors.on if self._checked else self._colors.off
        p.setPen(QPen(self._colors.ring, 1))
        p.setBrush(fill)
        p.drawEllipse(cx - r // 2, cy - r // 2, r, r)

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
