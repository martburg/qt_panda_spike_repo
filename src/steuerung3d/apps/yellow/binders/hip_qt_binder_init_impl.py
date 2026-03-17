from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton, QWidget

from steuerung3d.protocol.estop_bits import ESTOP_SPECS

from ..engines.hip.attach_state import NOT_ATTACHED
from ..qtutil.binder_helpers import block_signals, safe_set_text
from ..qtutil.ui_contract import log_missing_required_once
from ..qtutil.ui_panel_state import clear_line_edits, neutralize_dots, uncheck_checkboxes
from ..qtutil.ui_update import set_state_by_object_name, set_state_property
from .hip_qt_binder_init_support import (
    build_bindings as _build_bindings_support,
    disable_action_buttons,
    discover_estop_checkboxes,
    discover_widgets,
    log_binder_missing,
    setup_modal_and_params,
    setup_widget_cache,
)

if TYPE_CHECKING:
    from .hip_qt_binder import HipQtBinder


def post_init(self: "HipQtBinder") -> None:
    setup_widget_cache(self)
    discover_widgets(self)
    discover_estop_checkboxes(self)
    disable_action_buttons(self)
    setup_modal_and_params(self)
    _build_bindings(self)
    _log_binder_missing(self)
    log_missing_required_once(
        self.log,
        self._wcache,
        [(QComboBox, "cmbAxis"), (QLineEdit, "txtTick")],
        context="hi_p:required",
    )
    self._wire_signals()


def _build_bindings(self: "HipQtBinder") -> None:
    _build_bindings_support(self)


def _log_binder_missing(self: "HipQtBinder") -> None:
    log_binder_missing(self)


def wire_signals(self: "HipQtBinder") -> None:
    if self._cmbAxis is not None:
        self._suppress_axis_signal = True
        try:
            with block_signals(self._cmbAxis):
                self._cmbAxis.clear()
                self._cmbAxis.addItems([NOT_ATTACHED])
                self._cmbAxis.setCurrentText(NOT_ATTACHED)
        finally:
            self._suppress_axis_signal = False
        self._cmbAxis.currentTextChanged.connect(self._on_axis_selected)
    if self._btn_estop_reset is not None:
        self._btn_estop_reset.clicked.connect(self._on_estop_reset_clicked)
    if self._btn_diag_resync is not None:
        self._btn_diag_resync.clicked.connect(self._on_resync_clicked)
    btn_main_reset = getattr(self, "_btn_main_reset", None)
    if isinstance(btn_main_reset, QPushButton):
        sig = getattr(btn_main_reset, "clicked", None)
        if sig is not None:
            sig.connect(self._on_main_reset_clicked)
    btn_guider_reset = getattr(self, "_btn_guider_reset", None)
    if isinstance(btn_guider_reset, QPushButton):
        sig = getattr(btn_guider_reset, "clicked", None)
        if sig is not None:
            sig.connect(self._on_guider_reset_clicked)
    for grp, (b_edit, b_write, b_cancel) in {
        "pos": ("btnPosEdit", "btnPosWrite", "btnPosCancel"),
        "vel": ("btnVelEdit", "btnVelWrite", "btnVelCancel"),
        "filter": ("btnFilterEdit", "btnFilterWrite", "btnFilterCancel"),
        "guider": ("btnGuiderEdit", "btnGuiderWrite", "btnGuiderCancel"),
    }.items():
        be = self._find_button(b_edit)
        bw = self._find_button(b_write)
        bc = self._find_button(b_cancel)
        if be is not None:
            be.clicked.connect(lambda _=False, g=grp: self._on_param_action("edit", g))
        if bw is not None:
            bw.clicked.connect(lambda _=False, g=grp: self._on_param_action("write", g))
        if bc is not None:
            bc.clicked.connect(lambda _=False, g=grp: self._on_param_action("cancel", g))


def find_button(self: "HipQtBinder", object_name: str) -> QPushButton | None:
    return self._wcache.button(object_name)


def find_line_edit(self: "HipQtBinder", object_name: str) -> QLineEdit | None:
    return self._wcache.line_edit(object_name)


def require_widget(widget: QWidget | None, object_name: str) -> QWidget:
    if widget is None:
        raise RuntimeError(f"UI is missing widget named '{object_name}'")
    return widget


def set_dot(self: "HipQtBinder", object_name: str, state) -> None:
    if not object_name:
        return
    try:
        ww = self._wcache.widget(object_name)
        if ww is not None:
            set_state_property(ww, state)
            return
    except Exception:
        pass
    set_state_by_object_name(self.win, object_name, state)


def set_all_estop_unknown(self: "HipQtBinder") -> None:
    for spec in ESTOP_SPECS.values():
        if spec.dot:
            self._set_dot(spec.dot, "warn")


def clear_for_unattached(self: "HipQtBinder") -> None:
    keep = [self._txtTick] if self._txtTick is not None else []
    clear_line_edits(self.win, keep=keep, text="")
    safe_set_text(self._txtTick, "--")
    for w in (
        self._txt_main_amp_status,
        self._txt_slave_amp_status,
        self._txt_hdr_banner_left,
        self._txt_hdr_banner_right,
    ):
        safe_set_text(w, "")
    neutralize_dots(
        self._set_dot, ("dotHdrOnline", "dotHdrReady", "dotHdrFbt", "dotHdrBrake1", "dotHdrBrake2")
    )
    neutralize_dots(self._set_dot, [s.dot for s in ESTOP_SPECS.values() if s.dot])
    uncheck_checkboxes(getattr(self, "_estop_checks", {}).values())
