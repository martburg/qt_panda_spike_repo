"""Qt-only helpers for Yellow app."""

from __future__ import annotations

from .._lazy_exports import resolve_lazy_export

__all__ = [
    "WidgetCache",
    "ModalLock",
    "ParamWidgetBinder",
    "ParamUiBindings",
    "apply_param_ui",
    "safe_set_text",
    "block_signals",
    "set_text",
    "set_enabled",
    "update_slider",
]

_EXPORTS = {
    "WidgetCache": ("steuerung3d.apps.yellow.qtutil.widget_cache", "WidgetCache"),
    "ModalLock": ("steuerung3d.apps.yellow.qtutil.modal_lock", "ModalLock"),
    "ParamWidgetBinder": (
        "steuerung3d.apps.yellow.qtutil.param_widget_binder",
        "ParamWidgetBinder",
    ),
    "ParamUiBindings": ("steuerung3d.apps.yellow.qtutil.param_ui_apply", "ParamUiBindings"),
    "apply_param_ui": ("steuerung3d.apps.yellow.qtutil.param_ui_apply", "apply_param_ui"),
    "safe_set_text": ("steuerung3d.apps.yellow.qtutil.binder_helpers", "safe_set_text"),
    "block_signals": ("steuerung3d.apps.yellow.qtutil.binder_helpers", "block_signals"),
    "set_text": ("steuerung3d.apps.yellow.qtutil.ui_update", "set_text"),
    "set_enabled": ("steuerung3d.apps.yellow.qtutil.ui_update", "set_enabled"),
    "update_slider": ("steuerung3d.apps.yellow.qtutil.ui_update", "update_slider"),
}


def __getattr__(name: str):
    return resolve_lazy_export(name, _EXPORTS)
