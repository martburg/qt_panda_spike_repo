"""Param UI orchestration helpers for Yellow (Qt-bound)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from ..domain.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS
from .modal_lock import ModalLock
from .param_widget_binder import ParamWidgetBinder
from .ui_update import set_enabled, set_enabled_repolish


@dataclass(frozen=True)
class ParamUiBindings:
    win: Any
    modal_lock: ModalLock | None
    param_binder: ParamWidgetBinder
    find_line_edit: Callable[[str], Any | None]
    find_button: Callable[[str], Any | None]
    format_limit_value: Callable[[float], str]


def apply_param_ui(bindings: ParamUiBindings, vm: Any) -> None:
    if getattr(vm, "param_ui", None) is not None:
        param_ui = vm.param_ui
        _apply_modal_param_lock(
            bindings.modal_lock,
            active=bool(getattr(param_ui, "modal_lock_active", False)),
            group=str(getattr(param_ui, "modal_lock_group", "") or ""),
            find_line_edit=bindings.find_line_edit,
            find_button=bindings.find_button,
        )

        for group, gstate in dict(getattr(param_ui, "groups", {}) or {}).items():
            _set_param_group_enabled(
                str(group), bool(gstate.fields_enabled), bindings.find_line_edit
            )
            _set_param_button_state(str(group), gstate.buttons, bindings.find_button)

    param_values = getattr(vm, "param_values", None)
    if param_values:
        bindings.param_binder.apply_param_values(
            param_values,
            freeze_group=str(getattr(vm, "param_freeze_group", "") or ""),
            skip_focused=True,
            block_signals=True,
        )

    param_writeback_values = getattr(vm, "param_writeback_values", None)
    param_writeback_group = getattr(vm, "param_writeback_group", None)
    if param_writeback_values and param_writeback_group:
        bindings.param_binder.apply_param_values(
            param_writeback_values,
            freeze_group=str(param_writeback_group or ""),
            skip_focused=False,
            block_signals=True,
        )
        param_writeback_message = getattr(vm, "param_writeback_message", None)
        if param_writeback_message:
            _message_box_information(
                bindings.win,
                "Position limits adjusted",
                str(param_writeback_message),
            )

    dlg = getattr(vm, "param_commit_dialog", None)
    if dlg is not None:
        if str(getattr(dlg, "level", "")).lower() == "warning":
            _message_box_warning(bindings.win, str(dlg.title), str(dlg.message))
        else:
            _message_box_information(bindings.win, str(dlg.title), str(dlg.message))

    limit_values = getattr(vm, "limit_values", None)
    if limit_values:
        bindings.param_binder.apply_limit_values(
            limit_values,
            format_value=bindings.format_limit_value,
        )


def _apply_modal_param_lock(
    modal_lock: ModalLock | None,
    *,
    active: bool,
    group: str,
    find_line_edit: Callable[[str], Any | None],
    find_button: Callable[[str], Any | None],
) -> None:
    if modal_lock is None:
        return

    if active:
        allow: list[Any] = []
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

        modal_lock_any: Any = modal_lock
        modal_lock_any.lock(allow=allow)
        return

    modal_lock.unlock()


def _set_param_group_enabled(
    group: str,
    enabled: bool,
    find_line_edit: Callable[[str], Any | None],
) -> None:
    mapping: Mapping[str, str] = _PARAM_WIDGETS.get(group, {})
    for _key, obj_name in mapping.items():
        le = find_line_edit(obj_name)
        if le is None:
            continue
        set_enabled_repolish(le, bool(enabled))


def _set_param_button_state(
    group: str, buttons: Any, find_button: Callable[[str], Any | None]
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


def _message_box_information(parent: Any, title: str, message: str) -> None:
    try:
        from importlib import import_module

        QMessageBoxAny: Any = import_module("PySide6.QtWidgets").QMessageBox
        QMessageBoxAny.information(parent, title, message)
    except Exception:
        return


def _message_box_warning(parent: Any, title: str, message: str) -> None:
    try:
        from importlib import import_module

        QMessageBoxAny: Any = import_module("PySide6.QtWidgets").QMessageBox
        QMessageBoxAny.warning(parent, title, message)
    except Exception:
        return
