"""Qt-only helpers for Yellow app."""

from __future__ import annotations

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


def __getattr__(name: str):
	if name in ("WidgetCache",):
		from .widget_cache import WidgetCache  # type: ignore

		return locals()[name]
	if name in ("ModalLock",):
		from .modal_lock import ModalLock  # type: ignore

		return locals()[name]
	if name in ("ParamWidgetBinder",):
		from .param_widget_binder import ParamWidgetBinder  # type: ignore

		return locals()[name]
	if name in ("ParamUiBindings", "apply_param_ui"):
		from .param_ui_apply import ParamUiBindings, apply_param_ui  # type: ignore

		return locals()[name]
	if name in ("safe_set_text", "block_signals"):
		from .binder_helpers import block_signals, safe_set_text  # type: ignore

		return locals()[name]
	if name in ("set_text", "set_enabled", "update_slider"):
		from .ui_update import set_enabled, set_text, update_slider  # type: ignore

		return locals()[name]
	raise AttributeError(name)
