"""Widget reference bundle for HiP Qt binder.

Goal: keep widget discovery in one place, so init/apply code can stay mostly
pure (mapping VM -> widget state) and the binder has fewer ad-hoc attributes.

This is a refactor-only seam: the binder still exposes legacy attributes for
compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QAbstractSlider,
    QComboBox,
    QFrame,
    QLineEdit,
    QPushButton,
    QTabWidget,
)

from ..qtutil.widget_cache import WidgetCache


@dataclass(frozen=True)
class HipQtWidgets:
    tabs_main: QTabWidget | None
    cmb_axis: QComboBox | None
    frame_footer: QFrame | None
    frame_header: QFrame | None
    txt_tick: QLineEdit | None
    sld_vel_cmd: QAbstractSlider | None
    btn_estop_reset: QPushButton | None
    btn_diag_resync: QPushButton | None

    @staticmethod
    def from_cache(cache: WidgetCache) -> "HipQtWidgets":
        return HipQtWidgets(
            tabs_main=cache.get(QTabWidget, "tabsMain"),
            cmb_axis=cache.combo_box("cmbAxis"),
            frame_footer=cache.get(QFrame, "frameFooter"),
            frame_header=cache.get(QFrame, "frameHeader"),
            txt_tick=cache.line_edit("txtTick"),
            sld_vel_cmd=cache.slider("sldVelCmd"),
            btn_estop_reset=cache.button("btnEStopReset"),
            btn_diag_resync=cache.button("btnDiagResync"),
        )
