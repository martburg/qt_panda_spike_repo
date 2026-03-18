"""Qt-only binder for DenSi.

Responsibilities:
- Discover widgets.
- Wire signals for UI actions.
- Read UI inputs into DensiInputs.
- Apply DensiViewModel to the UI.

Business rules and state-machine logic must live in the runtime/engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QAbstractSlider, QComboBox, QLineEdit, QPushButton, QWidget

from ..engines.densi.inputs import DensiInputs, DensiUiInputs
from ..engines.densi.viewmodel import DensiViewModel
from . import densi_qt_binder_support as _support

if TYPE_CHECKING:
    from ..panels.densi.densi_banner_render import DenSiBannerBindings
    from ..panels.densi.densi_cut_markers_render import DenSiCutMarkersBindings
    from ..panels.densi.densi_estop_checkboxes_render import DenSiEstopCheckboxBindings
    from ..panels.densi.densi_readouts_render import DenSiReadoutsBindings
    from ..qtutil.param_widget_binder import ParamWidgetBinder
    from ..qtutil.widget_cache import WidgetCache


@dataclass
class DenSiQtBinder:
    win: QWidget
    log: logging.Logger
    axis_ids: list[str]

    _ui_actions: DensiUiInputs = field(default_factory=DensiUiInputs)
    _estop_cb_bindings: DenSiEstopCheckboxBindings | None = None
    _wcache: WidgetCache = field(init=False)
    _param_binder: ParamWidgetBinder = field(init=False)
    _b_readouts: DenSiReadoutsBindings = field(init=False)
    _b_banner: DenSiBannerBindings = field(init=False)
    _b_cut_markers: DenSiCutMarkersBindings = field(init=False)
    _txtTick: QLineEdit | None = None
    _txt_hdr_banner_left: QLineEdit | None = None
    _txt_hdr_banner_right: QLineEdit | None = None
    _txtPos: QLineEdit | None = None
    _txtVel: QLineEdit | None = None
    _txtAmp: QLineEdit | None = None
    _txtTemp: QLineEdit | None = None
    _txtCutPos: QLineEdit | None = None
    _txtCutVel: QLineEdit | None = None
    _txtCutTime: QLineEdit | None = None
    _txtPosdiff: QLineEdit | None = None
    _txt_guider_range_min: QLineEdit | None = None
    _txt_guider_range_max: QLineEdit | None = None
    _txt_guider_range_val: QLineEdit | None = None
    _txt_guider_speed: QLineEdit | None = None
    _sld_vel_cmd: QAbstractSlider | None = None
    _sld_limit_range: QAbstractSlider | None = None
    _btn_diag_resync: QPushButton | None = None
    _btn_es_start: QPushButton | None = None
    _btn_estop_all_set: QPushButton | None = None
    _btn_estop_all_clear: QPushButton | None = None
    _cmbAxis: QComboBox | None = None

    def __post_init__(self) -> None:
        _support.post_init(self)

    def _require_param_binder(self) -> ParamWidgetBinder:
        binder = self._param_binder
        if binder is None:
            raise RuntimeError("DenSiQtBinder parameter binder is not initialized")
        return binder

    def seed_params_from_ui(self) -> dict[str, float]:
        return self._require_param_binder().read_all_values()

    def lock_param_ui_device_side(self) -> None:
        btn_names = [
            "btnPosEdit",
            "btnPosWrite",
            "btnPosCancel",
            "btnVelEdit",
            "btnVelWrite",
            "btnVelCancel",
            "btnFilterEdit",
            "btnFilterWrite",
            "btnFilterCancel",
            "btnGuiderEdit",
            "btnGuiderWrite",
            "btnGuiderCancel",
        ]
        from ..domain.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS
        from ..qtutil.ui_update import set_enabled, set_state_property

        for name in btn_names:
            b = self._wcache.button(name)
            if b is not None:
                set_enabled(b, False)
        for _grp, _mapping in _PARAM_WIDGETS.items():
            for _key, _wname, _obj, le in self._require_param_binder().iter_param_line_edits():
                set_state_property(le, "true", prop="paramField")
                set_enabled(le, False)
            break

    def init_fixed_axis(self) -> None:
        _support.init_fixed_axis(self)

    def init_estop_checkboxes(self, *, estop_word: int) -> None:
        _support.init_estop_checkboxes(self, estop_word=estop_word)

    def reset_ui_startup(self) -> None:
        _support.reset_ui_startup(self)

    def read_inputs(self) -> DensiInputs:
        ui = self._ui_actions
        self._ui_actions = DensiUiInputs()
        return DensiInputs(frames=[], now_ns=0, ui=ui)

    def apply(self, vm: DensiViewModel) -> None:
        _support.apply_view_model(self, vm)

    def _wire_signals(self) -> None:
        _support.wire_signals(self)

    def _on_es_start_clicked(self) -> None:
        self._ui_actions.es_start_clicked = True

    def _on_estop_all_set_clicked(self) -> None:
        self._ui_actions.estop_all_set_clicked = True

    def _on_estop_all_clear_clicked(self) -> None:
        self._ui_actions.estop_all_clear_clicked = True

    def _on_diag_resync_clicked(self) -> None:
        self._ui_actions.diag_resync_clicked = True

    def _on_estop_checkbox_toggled(self, key: str, checked: bool) -> None:
        _support.on_estop_checkbox_toggled(self, key, checked)

    def _find_line_edit(self, object_name: str) -> QLineEdit | None:
        return _support.find_line_edit(self, object_name)

    def _set_dot(self, object_name: str, state: object) -> None:
        _support.set_dot(self, object_name, state)
