from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QFile, QTimer
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSlider,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QWidget,
)

from .qss_loader import load_base_qss

# Role-specific canvas tint (ONLY centralwidget background)
IP_BG  = "#E6F2FF"  # light sky blue
CFC_BG = "#E8FFF1"  # light mint

QSS_ROLE_IP = r"""
/* IP (HMI) background: deep blue */
QMainWindow[appRole="ip"],
QMainWindow[appRole="ip"] QWidget#centralwidget {
    background: #1f3550;
}
"""

QSS_ROLE_CFC = r"""
/* CFC (Sim) background: deep purple */
QMainWindow[appRole="cfc"],
QMainWindow[appRole="cfc"] QWidget#centralwidget {
    background: #E8FFF1;
}
"""


def parse_role(argv: list[str]) -> str:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--role", choices=("ip", "cfc"), default="ip")
    args, _rest = p.parse_known_args(argv[1:])
    return args.role

def _refit_window_height_only(win: QWidget) -> None:
    w = win.window() or win
    cw = getattr(w, "centralWidget", None)
    if callable(cw) and cw():
        if cw().layout():
            cw().layout().activate()
        cw().adjustSize()

    w.adjustSize()
    w.resize(w.width(), max(w.minimumSizeHint().height(), w.sizeHint().height()))

def load_ui(path: Path):
    loader = QUiLoader()
    f = QFile(str(path))
    if not f.open(QFile.ReadOnly):
        raise RuntimeError(f"Could not open UI file: {path}")
    try:
        w = loader.load(f, None)
    finally:
        f.close()
    if w is None:
        raise RuntimeError(f"QUiLoader failed to load: {path}")
    return w


def _pretty_name(obj_name: str) -> str:
    """Make a readable label from an objectName (best-effort)."""
    s = obj_name
    # strip common prefixes
    for prefix in (
        "btn",
        "txt",
        "chk",
        "cb",
        "cmb",
        "sld",
        "spin",
        "dbl",
        "gb",
        "frm",
        "frame",
        "lbl",
    ):
        if s.startswith(prefix) and len(s) > len(prefix):
            s = s[len(prefix) :]
            break
    # split camelCase-ish and underscores
    out = []
    buf = ""
    for ch in s:
        if ch == "_":
            if buf:
                out.append(buf)
                buf = ""
            continue
        if ch.isupper() and buf:
            out.append(buf)
            buf = ch
        else:
            buf += ch
    if buf:
        out.append(buf)
    return " ".join(w.capitalize() for w in out if w)


def apply_tooltips(win: QWidget) -> None:
    """Attach tooltips everywhere (high-quality where we know, sensible fallback elsewhere)."""

    # High-value explicit tooltips (kept short, action-oriented).
    explicit: dict[str, str] = {
        "btnSetupToggle": "Show/hide the Setup panel (advanced parameters and diagnostics).",
        "btnEStopAllSet": "Set ALL simulated E-Stop bits (forces E-Stop active in the simulator).",
        "btnEStopAllClear": "Clear ALL simulated E-Stop bits (release E-Stop in the simulator).",
        "btnPosSet_set": "Apply the position setpoint (Set).",
        "btnVelSet_3_set": "Apply velocity/acceleration limits (Set).",
        "btnFilterSet_set": "Apply filter parameters (Set).",
        "btnRopeSet_set": "Apply rope parameters (Set).",
    }

    # First pass: explicit mapping
    for name, tip in explicit.items():
        w = win.findChild(QWidget, name)
        if w is not None:
            w.setToolTip(tip)

    # Second pass: fill in missing tooltips with sensible defaults
    for w in win.findChildren(QWidget):
        if w.toolTip():
            continue
        name = w.objectName() or ""
        if not name:
            continue
        pretty = _pretty_name(name)

        # Avoid spamming containers/frames with generic tooltips
        if isinstance(w, (QFrame, QLabel)):
            continue

        if isinstance(w, QPushButton):
            w.setToolTip(f"Action: {pretty}.")
        elif isinstance(w, QCheckBox):
            w.setToolTip(f"Toggle: {pretty}.")
        elif isinstance(w, QLineEdit):
            w.setToolTip(f"Input: {pretty}.")
        elif isinstance(w, QComboBox):
            w.setToolTip(f"Select: {pretty}.")
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            w.setToolTip(f"Set value: {pretty}.")
        elif isinstance(w, QAbstractSlider):
            w.setToolTip(f"Adjust: {pretty}.")
        elif isinstance(w, QAbstractButton):
            # tool buttons, radio buttons, etc.
            w.setToolTip(f"Control: {pretty}.")

def build_yellow_window(*, role: str, ui_path=None):
    """Build the Yellow window (view shell only).

    This function owns only presentation concerns (QSS, role title, setup toggle, tooltips).
    Role-specific logic belongs in HI-P / Den-Si controllers.
    """

    if ui_path is None:
        ui_path = Path(__file__).with_name("assets") / "yellow3_merged.ui"
    win = load_ui(Path(ui_path))
    # Hide Diagnostics tab in IP role (HMI client)
    if role == "ip":
        tabs_main = win.findChild(QTabWidget, "tabsMain")
        page_diag = win.findChild(QWidget, "pageDiagnostics")
        if tabs_main is not None and page_diag is not None:
            idx = tabs_main.indexOf(page_diag)
            if idx >= 0:
                if hasattr(tabs_main, "setTabVisible"):
                    tabs_main.setTabVisible(idx, False)
                else:
                    tabs_main.setTabEnabled(idx, False)
    win.setProperty("appRole", role)
    # Title
    title = "HMI – Intent Producer (IP)" if role == "ip" else "SIM – CommandFrame Consumer (CFC)"
    win.setWindowTitle(title)


    # --- Setup toggle via button ---
    btn = win.findChild(QPushButton, "btnSetupToggle")
    panel = win.findChild(QWidget, "frameSetup")

    if btn is None:
        raise RuntimeError("UI is missing widget named 'btnSetupToggle'")
    if panel is None:
        raise RuntimeError("UI is missing widget named 'frameSetup'")

    panel.setVisible(False)

    def update_button_text():
        # Make it explicit what will happen when clicked.
        btn.setText("Close Setup ▲" if panel.isVisible() else "Open Setup ▼")

    def toggle_setup():
        panel.setVisible(not panel.isVisible())
        update_button_text()
        QTimer.singleShot(0, lambda: _refit_window_height_only(win))

    btn.clicked.connect(toggle_setup)
    update_button_text()
    # --- end toggle ---

    apply_tooltips(win)

    win.setMinimumSize(0, 0)

    bg = IP_BG if role == "ip" else CFC_BG

    base_qss = load_base_qss()
    role_qss = f"""
    QMainWindow[appRole="{role}"] QWidget#centralwidget {{
        background: {bg};
    }}
    """
    win.setStyleSheet(base_qss + role_qss)
    QTimer.singleShot(0, lambda: _refit_window_height_only(win))
    return win



__all__ = [
    'build_yellow_window',
    'load_ui',
    'apply_tooltips',
]
