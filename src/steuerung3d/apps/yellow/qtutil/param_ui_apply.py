"""Param UI orchestration helpers for Yellow (Qt-bound)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from PySide6.QtWidgets import QLineEdit, QMessageBox, QPushButton, QWidget

from ..domain.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS
from .modal_lock import ModalLock
from .param_widget_binder import ParamWidgetBinder
from .ui_update import set_enabled, set_enabled_repolish


@dataclass(frozen=True)
class ParamUiBindings:
    win: QWidget
    modal_lock: ModalLock | None
    param_binder: ParamWidgetBinder
    find_line_edit: Callable[[str], QLineEdit | None]
    find_button: Callable[[str], QPushButton | None]
    format_limit_value: Callable[[float], str]


def apply_param_ui(bindings: ParamUiBindings, vm) -> None:
    if vm.param_ui is not None:
        _apply_modal_param_lock(
            bindings.modal_lock,
            active=bool(vm.param_ui.modal_lock_active),
            group=str(vm.param_ui.modal_lock_group or ""),
            find_line_edit=bindings.find_line_edit,
            find_button=bindings.find_button,
        )

        for group, gstate in (vm.param_ui.groups or {}).items():
            _set_param_group_enabled(group, bool(gstate.fields_enabled), bindings.find_line_edit)
            _set_param_button_state(group, gstate.buttons, bindings.find_button)

    if vm.param_values:
        bindings.param_binder.apply_param_values(
            vm.param_values,
            freeze_group=str(vm.param_freeze_group or ""),
            skip_focused=True,
            block_signals=True,
        )

    if vm.param_writeback_values and vm.param_writeback_group:
        bindings.param_binder.apply_param_values(
            vm.param_writeback_values,
            freeze_group=str(vm.param_writeback_group or ""),
            skip_focused=False,
            block_signals=True,
        )
        if vm.param_writeback_message:
            QMessageBox.information(
                bindings.win,
                "Position limits adjusted",
                str(vm.param_writeback_message),
            )

    if vm.param_commit_dialog is not None:
        dlg = vm.param_commit_dialog
        if str(dlg.level).lower() == "warning":
            QMessageBox.warning(bindings.win, str(dlg.title), str(dlg.message))
        else:
            QMessageBox.information(bindings.win, str(dlg.title), str(dlg.message))

    if vm.limit_values:
        bindings.param_binder.apply_limit_values(
            vm.limit_values,
            format_value=bindings.format_limit_value,
        )


def _apply_modal_param_lock(
    modal_lock: ModalLock | None,
    *,
    active: bool,
    group: str,
    find_line_edit: Callable[[str], QLineEdit | None],
    find_button: Callable[[str], QPushButton | None],
) -> None:
    if modal_lock is None:
        return

    if active:
        allow: list[QWidget] = []
        for _k, obj_name in _PARAM_WIDGETS.get(group, {}).items():
            le = find_line_edit(obj_name)
            if le is not None:
                allow.append(le)

        wiring = {
            "pos": ("btnPosWrite", "btnPosCancel"),
            "vel": ("btnVelWrite", "btnVelCancel"),
            "filter": ("btnFilterWrite", "btnFilterCancel"),
            "guider": ("btnGuiderWrite", "btnGuiderCancel"),
        }
        if group in wiring:
            bw = find_button(wiring[group][0])
            bc = find_button(wiring[group][1])
            if bw is not None:
                allow.append(bw)
            if bc is not None:
                allow.append(bc)

        modal_lock.lock(allow=allow)
        return

    modal_lock.unlock()


def _set_param_group_enabled(
    group: str,
    enabled: bool,
    find_line_edit: Callable[[str], QLineEdit | None],
) -> None:
    mapping: Mapping[str, str] = _PARAM_WIDGETS.get(group, {})
    for _key, obj_name in mapping.items():
        le = find_line_edit(obj_name)
        if le is None:
            continue
        set_enabled_repolish(le, bool(enabled))


def _set_param_button_state(
    group: str, buttons, find_button: Callable[[str], QPushButton | None]
) -> None:
    wiring = {
        "pos": ("btnPosEdit", "btnPosWrite", "btnPosCancel"),
        "vel": ("btnVelEdit", "btnVelWrite", "btnVelCancel"),
        "filter": ("btnFilterEdit", "btnFilterWrite", "btnFilterCancel"),
        "guider": ("btnGuiderEdit", "btnGuiderWrite", "btnGuiderCancel"),
    }
    if group not in wiring:
        return
    b_edit, b_write, b_cancel = wiring[group]
    be = find_button(b_edit)
    bw = find_button(b_write)
    bc = find_button(b_cancel)
    if be is not None:
        set_enabled(be, bool(buttons.edit_enabled))
    if bw is not None:
        set_enabled(bw, bool(buttons.write_enabled))
    if bc is not None:
        set_enabled(bc, bool(buttons.cancel_enabled))
