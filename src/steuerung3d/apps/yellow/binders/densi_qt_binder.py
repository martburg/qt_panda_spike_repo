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

from PySide6.QtWidgets import QLineEdit, QWidget

from ..engines.densi.inputs import DensiInputs, DensiUiInputs
from ..engines.densi.viewmodel import DensiViewModel
from . import densi_qt_binder_support as _support


@dataclass
class DenSiQtBinder:
    win: QWidget
    log: logging.Logger
    axis_ids: list[str]

    _ui_actions: DensiUiInputs = field(default_factory=DensiUiInputs)
    _estop_cb_bindings: object | None = None

    def __post_init__(self) -> None:
        _support.post_init(self)

    def seed_params_from_ui(self) -> dict[str, float]:
        return self._param_binder.read_all_values()

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
            for _key, _wname, _obj, le in self._param_binder.iter_param_line_edits():
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

    def _set_dot(self, object_name: str, state) -> None:
        _support.set_dot(self, object_name, state)
