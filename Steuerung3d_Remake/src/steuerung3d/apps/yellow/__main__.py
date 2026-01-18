from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QFile, QTimer
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QLayout
from PySide6.QtWidgets import QApplication, QWidget, QPushButton
from PySide6.QtWidgets import QFrame, QLabel

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

/* your “yellow strip” blocks that should NOT be red-tinted (you said you fixed by hand) */
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
QLineEdit#txtVelMaxMot, QLineEdit#txtLagError { color: #c00000; font-weight: bold; }

QPushButton {
    background: #efefef;
    border: 1px solid #555;
    border-radius: 6px;
    padding: 5px 10px;
}
QPushButton:pressed { background: #dcdcdc; }

QComboBox {
    background: #efefef;
    border: 1px solid #666;
    border-radius: 6px;
    padding: 4px 8px;
}

/* ===== LED dots: keep visible always ===== */
QFrame#led_fbt_dot, QFrame#led_ready_dot, QFrame#led_online_dot, QFrame#led_brk1_dot, QFrame#led_brk2_dot,
QFrame#dotMaster, QFrame#dotGuider, QFrame#dotNetwork,
QFrame#dotEStop1, QFrame#dotEStop2, QFrame#dot30kw, QFrame#dot05kw,
QFrame#dotBRK1, QFrame#dotBRK2, QFrame#dotBRK2KB,
QFrame#dotSPS, QFrame#dotRed, QFrame#dotENC,
QFrame#dotPosWin, QFrame#dotVelWin, QFrame#dotEndlage,
QFrame#g1_com_dot, QFrame#g1_fb_dot, QFrame#g1_out_dot,
QFrame#g2_com_dot, QFrame#g2_fb_dot, QFrame#g2_out_dot,
QFrame#g3_com_dot, QFrame#g3_fb_dot, QFrame#g3_out_dot {
    min-width: 12px; max-width: 12px;
    min-height: 12px; max-height: 12px;
    border-radius: 6px;
    background: #444;
    border: 1px solid #000;
}

/* ===== Tabs: neutral grey, NO red bleed ===== */
/* Scope strictly to setup tabs only */
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
    background: #e0e0e0}

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
"""

QSS_HDR_LED = r"""
/* Header LED dots (FBT/Ready/Online/Brake1/Brake2) */
#ledHdrFbtDot, #ledHdrReadyDot, #ledHdrOnlineDot, #ledHdrBrk1Dot,
#ledGuiderReadyDot, #ledGuiderOnlineDot,  #ledHdrBrk2Dot {
    min-width: 12px; max-width: 12px;
    min-height: 12px; max-height: 12px;
    border-radius: 6px;
    background: #444;
    border: 1px solid #000;
}
"""

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

def main() -> int:
    app = QApplication(sys.argv)
    ui_path = Path(__file__).with_name("yellow3.ui")
    win = load_ui(ui_path)
    win.setStyleSheet(QSS)

    # --- Setup toggle via button ---
    btn = win.findChild(QPushButton, "btnSetupToggle")
    panel = win.findChild(QWidget, "frameSetup")

    if btn is None:
        raise RuntimeError("UI is missing widget named 'btnSetupToggle'")
    if panel is None:
        raise RuntimeError("UI is missing widget named 'frameSetup'")

    panel.setVisible(False)

    def update_button_text():
        btn.setText("Setup ▼" if panel.isVisible() else "Setup ▶")

    def toggle_setup():
        panel.setVisible(not panel.isVisible())
        update_button_text()
        QTimer.singleShot(0, lambda: _refit_window_height_only(win))

    btn.clicked.connect(toggle_setup)
    update_button_text()
    # --- end toggle ---

    win.setMinimumSize(0, 0)
    win.setStyleSheet(QSS + QSS_HDR_LED)
    win.show()
    QTimer.singleShot(0, lambda: _refit_window_height_only(win))
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
