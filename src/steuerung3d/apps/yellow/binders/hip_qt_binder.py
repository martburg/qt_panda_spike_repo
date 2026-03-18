"""Qt-only binder for HiP.

Responsibilities:
- Discover widgets.
- Wire signals to capture UI actions.
- Read UI inputs into HipUiInputs.
- Apply HipViewModel to widgets.

Business rules and intent policy live in the engine/controller.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QAbstractSlider,
    QCheckBox,
    QComboBox,
    QFrame,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QWidget,
)

from ..domain.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS
from ..engines.hip.engine import (
    HipParamAction,
    HipUiInputs,
    HipViewModel,
)
from ..qtutil.modal_lock import ModalLock
from .hip_qt_widgets import HipQtWidgets

if TYPE_CHECKING:
    from ..panels.hip.hip_banner_render import HipBannerBindings
    from ..panels.hip.hip_cut_markers_render import HipCutMarkersBindings
    from ..panels.hip.hip_drive_status_render import HipDriveStatusBindings
    from ..panels.hip.hip_estop_render import HipEstopBindings
    from ..panels.hip.hip_header_dots_render import HipHeaderDotsBindings
    from ..panels.hip.hip_readouts_render import HipReadoutsBindings
    from ..panels.hip.hip_sliders_render import HipSlidersBindings
    from ..qtutil.param_ui_apply import ParamUiBindings
    from ..qtutil.param_widget_binder import ParamWidgetBinder
    from ..qtutil.widget_cache import WidgetCache

from . import hip_qt_binder_apply_impl as _apply_impl, hip_qt_binder_init_impl as _init_impl


def _empty_events() -> list[HipParamAction]:
    return []


def _empty_estop_checks() -> dict[str, QCheckBox]:
    return {}


@dataclass
class HipQtBinder:
    win: QWidget
    log: logging.Logger

    _events: list[HipParamAction] = field(default_factory=_empty_events)
    _estop_reset_clicked: bool = False
    _resync_clicked: bool = False
    _main_reset_clicked: bool = False
    _guider_reset_clicked: bool = False
    _axis_selection_changed: bool = False
    _axis_selected_value: str = ""
    _suppress_axis_signal: bool = False
    _banner_bindings: HipBannerBindings | None = None
    _estop_bindings: HipEstopBindings | None = None
    _header_dots_bindings: HipHeaderDotsBindings | None = None
    _cut_markers_bindings: HipCutMarkersBindings | None = None
    _drive_status_bindings: HipDriveStatusBindings | None = None
    _readouts_bindings: HipReadoutsBindings | None = None
    _sliders_bindings: HipSlidersBindings | None = None
    _modal_lock: ModalLock | None = None
    _param_ui_bindings: ParamUiBindings | None = None
    _param_binder: ParamWidgetBinder = field(init=False)
    _wcache: WidgetCache = field(init=False)
    _widgets: HipQtWidgets | None = None
    _estop_checks: dict[str, QCheckBox] = field(default_factory=_empty_estop_checks)
    _tabs_main: QTabWidget | None = None
    _cmbAxis: QComboBox | None = None
    _frame_footer: QFrame | None = None
    _frame_header: QFrame | None = None
    _txtTick: QLineEdit | None = None
    _txt_hdr_banner_left: QLineEdit | None = None
    _txt_hdr_banner_right: QLineEdit | None = None
    _txt_main_amp_status: QLineEdit | None = None
    _txt_slave_amp_status: QLineEdit | None = None
    _txtPos: QLineEdit | None = None
    _txtVel: QLineEdit | None = None
    _txtAmp: QLineEdit | None = None
    _txtTemp: QLineEdit | None = None
    _txtLimitHardMin: QLineEdit | None = None
    _txtLimitUserMin: QLineEdit | None = None
    _txtLimitUserMax: QLineEdit | None = None
    _txtLimitHardMax: QLineEdit | None = None
    _txtCutPos: QLineEdit | None = None
    _txtCutVel: QLineEdit | None = None
    _txtCutTime: QLineEdit | None = None
    _txtPosdiff: QLineEdit | None = None
    _txt_guider_range_min: QLineEdit | None = None
    _txt_guider_range_max: QLineEdit | None = None
    _txt_guider_range_val: QLineEdit | None = None
    _txt_guider_speed: QLineEdit | None = None
    _txtGuiderPosMin: QLineEdit | None = None
    _txtGuiderPosMax: QLineEdit | None = None
    _txtGuiderPitch: QLineEdit | None = None
    _sld_vel_cmd: QAbstractSlider | None = None
    _sld_limit_range: QAbstractSlider | None = None
    _sld_guider_range: QAbstractSlider | None = None
    _sld_guider_speed: QAbstractSlider | None = None
    _btn_estop_reset: QPushButton | None = None
    _btn_diag_resync: QPushButton | None = None
    _btn_main_reset: QPushButton | None = None
    _btn_guider_reset: QPushButton | None = None

    def __post_init__(self) -> None:
        _init_impl.post_init(self)

    def _require_param_binder(self) -> ParamWidgetBinder:
        binder = self._param_binder
        if binder is None:
            raise RuntimeError("HipQtBinder parameter binder is not initialized")
        return binder

    # ------------------------------------------------------------------
    # Signal wiring / input capture
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        _init_impl.wire_signals(self)

    def _on_estop_reset_clicked(self) -> None:
        self._estop_reset_clicked = True

    def _on_resync_clicked(self) -> None:
        self._resync_clicked = True

    def _on_main_reset_clicked(self) -> None:
        self._main_reset_clicked = True

    def _on_guider_reset_clicked(self) -> None:
        self._guider_reset_clicked = True

    def _on_axis_selected(self, axis_id: str) -> None:
        if self._suppress_axis_signal:
            return
        self._axis_selection_changed = True
        self._axis_selected_value = str(axis_id or "").strip()

    def _on_param_action(self, kind: str, group: str) -> None:
        self._events.append(HipParamAction(kind=str(kind), group=str(group)))

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------

    def read_inputs(self) -> HipUiInputs:
        axis_selected = ""
        if self._cmbAxis is not None:
            try:
                axis_selected = str(self._cmbAxis.currentText() or "").strip()
            except Exception:
                axis_selected = ""

        events = list(self._events)
        self._events.clear()
        estop_reset_clicked = bool(self._estop_reset_clicked)
        resync_clicked = bool(self._resync_clicked)
        main_reset_clicked = bool(self._main_reset_clicked)
        guider_reset_clicked = bool(self._guider_reset_clicked)
        axis_selection_changed = bool(self._axis_selection_changed)
        if axis_selection_changed and self._axis_selected_value:
            axis_selected = self._axis_selected_value
        self._estop_reset_clicked = False
        self._resync_clicked = False
        self._main_reset_clicked = False
        self._guider_reset_clicked = False
        self._axis_selection_changed = False
        self._axis_selected_value = ""

        param_values: dict[str, dict[str, float]] = {}
        for group in _PARAM_WIDGETS.keys():
            param_values[group] = self._require_param_binder().read_group_values(group)

        return HipUiInputs(
            axis_selected=axis_selected,
            axis_selection_changed=axis_selection_changed,
            estop_reset_clicked=estop_reset_clicked,
            resync_clicked=resync_clicked,
            main_reset_clicked=main_reset_clicked,
            guider_reset_clicked=guider_reset_clicked,
            param_actions=events,
            param_values=param_values,
        )

    # ------------------------------------------------------------------
    # Apply VM
    # ------------------------------------------------------------------

    def apply(self, vm: HipViewModel) -> None:
        _apply_impl.apply(self, vm)

    def apply_startup_state(self) -> None:
        _apply_impl.apply_startup_state(self)

    def apply_tick_text(self, text: str) -> None:
        _apply_impl.apply_tick_text(self, text)

    def apply_online_state(self, state: str | None) -> None:
        _apply_impl.apply_online_state(self, state)

    def _apply_attach_combo(self, vm: HipViewModel) -> None:
        _apply_impl._apply_attach_combo(self, vm)

    def _set_joy_properties(self, deadman: bool, select_hip: bool) -> None:
        _apply_impl._set_joy_properties(self, deadman, select_hip)

    def _apply_joy_speed(self, soll_speed: float) -> None:
        _apply_impl._apply_joy_speed(self, soll_speed)

    # ------------------------------------------------------------------
    # Apply helpers
    # ------------------------------------------------------------------

    def _apply_attach_state(self, vm: HipViewModel) -> None:
        _apply_impl._apply_attach_state(self, vm)

    def _apply_drive_status(self, vm: HipViewModel) -> None:
        _apply_impl._apply_drive_status(self, vm)

    def _apply_banner(self, vm: HipViewModel) -> None:
        _apply_impl._apply_banner(self, vm)

    def _apply_header_dots(self, vm: HipViewModel) -> None:
        _apply_impl._apply_header_dots(self, vm)

    def _apply_estop_state(self, vm: HipViewModel) -> None:
        _apply_impl._apply_estop_state(self, vm)

    def _apply_readouts(self, vm: HipViewModel) -> None:
        _apply_impl._apply_readouts(self, vm)

    def _apply_sliders(self, vm: HipViewModel) -> None:
        _apply_impl._apply_sliders(self, vm)

    def _apply_cut_markers(self, vm: HipViewModel) -> None:
        _apply_impl._apply_cut_markers(self, vm)

    def _apply_params(self, vm: HipViewModel) -> None:
        _apply_impl._apply_params(self, vm)

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _init_param_inputs(self) -> None:
        self._param_binder.init_param_inputs()

    def _find_button(self, object_name: str) -> QPushButton | None:
        return _init_impl.find_button(self, object_name)

    def _find_line_edit(self, object_name: str) -> QLineEdit | None:
        return _init_impl.find_line_edit(self, object_name)

    def _build_bindings(self) -> None:
        _init_impl._build_bindings(self)

    @staticmethod
    def _require_widget(widget: QWidget | None, object_name: str) -> QWidget:
        return _init_impl.require_widget(widget, object_name)

    def _set_dot(self, object_name: str, state: object) -> None:
        _init_impl.set_dot(self, object_name, state)

    def _set_all_estop_unknown(self) -> None:
        _init_impl.set_all_estop_unknown(self)

    def _clear_for_unattached(self) -> None:
        _init_impl.clear_for_unattached(self)
