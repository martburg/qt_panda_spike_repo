from __future__ import annotations

import sys
import argparse
from pathlib import Path

from PySide6.QtCore import QFile, QTimer
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QLayout
from PySide6.QtWidgets import QTabWidget, QWidget, QPushButton
from PySide6.QtWidgets import QFrame, QLabel
from PySide6.QtWidgets import QAbstractButton, QLineEdit, QComboBox, QAbstractSlider
from PySide6.QtWidgets import QSpinBox, QDoubleSpinBox, QCheckBox

QSS = r"""
/* ===== palette tuned to legacy ===== */
QMainWindow { background: #7b2a2a; }  /* base behind frames */

/* main red frames */
#frameHeader, #frameFooter, #frameMain, #frameSetupToggle, #frameSetup {
    background: #a85151;              /* brick red that works w/ black+white text */
    border: 1px solid #000;
    border-radius: 10px;
}

/* guider speed box */
#frameGuiderSpeed, #frameGuiderRange { border: 1px solid #000; border-radius: 8px; }

/* yellow status column */
#frameStatusPanel {
    background: #f2c20c;
    border: 2px solid #000;
    border-radius: 10px;
}

/* “yellow strip” blocks that should NOT be red-tinted */
#frmMasterGuiderNetwork, #frmGComBlock, #frmYellowLeft, #frmYellowRight,
#frameStatusLeft, #frameStatusMid, #frameStatusRight, #frameStatusMasterBlock, #frameStatusGBlock {
    background: #d8d2b0;              /* warm grey/khaki */
    border: 2px solid #000;
    border-radius: 8px;
}

/* ===== group boxes ===== */
QGroupBox#gbPanel {
    background: #d9d9d9;
    border: 1px solid #000;
    border-radius: 8px;
    margin-top: 18px;
    color: #111;
}
QGroupBox#gbPanel::title {
    subcontrol-origin: margin;
    left: 10px;
    top: 4px;
    padding: 0 6px;
    color: #111;
    font-weight: 600;
}
QGroupBox#gbStatusFlagsTop,
QGroupBox#gbStatusFlags,
QGroupBox#gbSafetyFlags,
QGroupBox#gbTwinSafeFlags,
QGroupBox#gbGuiderFlags {
    background: rgba(255,255,255,0.22);
    border: 1px solid #000;
    border-radius: 8px;
}

/* ===== text ===== */
QLabel { color: #111; }
QLabel#lblUnit { color: #eee; font-weight: bold; }
QLabel[role="headerSmall"] { color: #f8f8f8; }

/* ===== inputs ===== */
QLineEdit {
    background: #efefef;
    border: 1px solid #666;
    border-radius: 4px;
    padding: 2px 6px;
    color: #111;
}

/* Parameter fields: HiP should turn white when active, light grey when disabled */
QLineEdit[paramField="true"]:enabled { background: #ffffff; }
QLineEdit[paramField="true"]:disabled { background: #d8d8d8; color: #555; }

QLineEdit#txtVelMaxMot, QLineEdit#txtLagError { color: #c00000; font-weight: bold; }

QComboBox {
    background: #efefef;
    border: 1px solid #666;
    border-radius: 6px;
    padding: 4px 8px;
}

/* ===== buttons (bevel + strong outline) ===== */
QPushButton, QToolButton {
    background: #e2e2e2;
    color: #111;

    border-style: solid;
    border-width: 2px;

    /* faux double-border / bevel */
    border-top-color: #ffffff;
    border-left-color: #ffffff;
    border-right-color: #2b2b2b;
    border-bottom-color: #2b2b2b;

    border-radius: 1px;
    padding: 6px 12px;
    margin: 4px;
}
QPushButton:hover, QToolButton:hover {
    background: #ededed;
    border-top-color: #ffffff;
    border-left-color: #ffffff;
    border-right-color: #1a1a1a;
    border-bottom-color: #1a1a1a;
}
QPushButton:pressed, QToolButton:pressed {
    background: #d0d0d0;

    border-top-color: #2b2b2b;
    border-left-color: #2b2b2b;
    border-right-color: #ffffff;
    border-bottom-color: #ffffff;

    padding-top: 7px;
    padding-left: 13px;
}
QPushButton:disabled, QToolButton:disabled {
    background:#dcdcdc;
    color: #888;
    border-top-color: #f5f5f5;
    border-left-color: #f5f5f5;
    border-right-color: #bdbdbd;
    border-bottom-color: #bdbdbd;
}

/* Danger */
QPushButton[kind="danger"], QToolButton[kind="danger"] {
    background: #c9a2a2;           /* desaturated warm red-grey */
    color: #111;

    border-style: solid;
    border-width: 2px;

    border-top-color: #f2e8e8;
    border-left-color: #f2e8e8;
    border-right-color: #3a1a1a;
    border-bottom-color: #3a1a1a;

    border-radius: 1px;
    padding: 6px 12px;
    margin: 4px;
    outline: none;
}
QPushButton[kind="danger"]:hover, QToolButton[kind="danger"]:hover {
    background: #b10000;
    color: #f2f2f2;
    border-right-color: #220c0c;
    border-bottom-color: #220c0c;
}
QPushButton[kind="danger"]:pressed, QToolButton[kind="danger"]:pressed {
    background: #b99f9f;

    border-top-color: #3a1a1a;
    border-left-color: #3a1a1a;
    border-right-color: #f2e8e8;
    border-bottom-color: #f2e8e8;

    padding-top: 7px;
    padding-left: 13px;
}
QPushButton[kind="danger"]:disabled, QToolButton[kind="danger"]:disabled {
    background: #cfc7c7;
    color: #777;
    border-right-color: #8a7a7a;
    border-bottom-color: #8a7a7a;
}

/* ===== LED dots: geometry only (NO color here) ===== */
QFrame#led_fbt_dot, QFrame#led_ready_dot, QFrame#led_online_dot,
QFrame#led_brk1_dot, QFrame#led_brk2_dot,
QFrame#dotMaster, QFrame#dotGuider, QFrame#dotNetwork,
QFrame#dotEStop1, QFrame#dotEStop2, QFrame#dot30kw, QFrame#dot05kw,
QFrame#dotBRK1, QFrame#dotBRK2, QFrame#dotBRK2KB,
QFrame#dotSPS, QFrame#dotRed, QFrame#dotENC,
QFrame#dotPosWin, QFrame#dotVelWin, QFrame#dotEndlage,
QFrame#g1_com_dot, QFrame#g1_fb_dot, QFrame#g1_out_dot,
QFrame#g2_com_dot, QFrame#g2_fb_dot, QFrame#g2_out_dot,
QFrame#g3_com_dot, QFrame#g3_fb_dot, QFrame#g3_out_dot,
QFrame#dotHdrFbt, QFrame#dotHdrReady, QFrame#dotHdrOnline,
QFrame#dotHdrBrake1, QFrame#dotHdrBrake2,
QFrame#ledGuiderReadyDot, QFrame#ledGuiderOnlineDot
{
    min-width: 12px; max-width: 12px;
    min-height: 12px; max-height: 12px;
    border-radius: 6px;
    border: 1px solid #000;
}

/* Default for any LED that has a state set (covers warn/good/bad/off etc.) */
QFrame[state] { background: #000; }  /* default = black */

/* State overrides */
QFrame[state="bad"]  { background: #d33; }  /* red */
QFrame[state="good"] { background: #3d3; }  /* green */
QFrame[state="warn"] { background: #ea0; }  /* amber */

/* ===== Tabs: neutral grey, NO red bleed ===== */
#frameSetup QTabWidget::pane {
    border: 1px solid #000;
    border-radius: 10px;
    background: #f2f2f2;
    top: -1px;
}

/* Make the actual tab pages neutral grey */
#frameSetup QTabWidget QWidget#pageGuider,
#frameSetup QTabWidget QWidget#pageParameters,
#frameSetup QTabWidget QWidget#pageDiagnostics,
#frameSetup QTabWidget QWidget#pageCommsTiming,
#frameSetup QTabWidget QWidget#pageLastFrames,
#frameSetup QTabWidget QWidget#pageFaultInject,
#frameSetup QTabWidget QWidget#pageEventsFaults,
#frameSetup QTabWidget QWidget#pageLogging {
    background: #e0e0e0;
}

/* Tab buttons (subtle grey, rounded) */
#frameSetup QTabBar::tab {
    border: 1px solid #000;
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 5px 12px;
    margin-right: 4px;
    background: #e0e0e0;
    color: #111;
}
#frameSetup QTabBar::tab:selected {
    background: #f7f7f7;
    margin-bottom: -1px;
    font-weight: 600;
}
#frameSetup QTabBar::tab:hover { background: #ebebeb; }

/* Diagnostics sub-tabs a touch smaller */
#tabsDiagnostics QTabBar::tab {
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 4px 10px;
}
/* Make only the E-Stop ALL buttons taller */
QPushButton#btnEStopAllSet,
QPushButton#btnEStopAllClear {
    min-height: 25px;     /* bump until it matches your visual row */
    padding-top: 0px;
    padding-bottom: 0px;
}
"""
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
        ui_path = Path(__file__).with_name("ui_split") / "yellow3_merged.ui"
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

    role_qss = f"""
    QMainWindow[appRole="{role}"] QWidget#centralwidget {{
        background: {bg};
    }}
    """
    win.setStyleSheet(QSS + role_qss )
    QTimer.singleShot(0, lambda: _refit_window_height_only(win))
    return win



__all__ = [
    'build_yellow_window',
    'load_ui',
    'apply_tooltips',
]
