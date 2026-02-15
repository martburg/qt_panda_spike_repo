# src/steuerung3d/apps/yellow/controllers/ui_state.py
from __future__ import annotations

from typing import Any
from PySide6.QtWidgets import QWidget


def _repolish(widget: QWidget) -> None:
    """Force QSS to re-evaluate dynamic properties on a widget."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_state_property(widget: QWidget, state: Any, prop: str = "state") -> None:
    """
    Set a dynamic Qt property used by QSS (e.g. state='on'/'off') and repolish.

    We keep this tiny and predictable because it's called often in the UI loop.
    """
    widget.setProperty(prop, state)
    _repolish(widget)


def set_state_by_object_name(
    root: QWidget,
    object_name: str,
    state: Any,
    prop: str = "state",
) -> None:
    """
    Find a child widget by objectName under `root` and apply `set_state_property`.

    Missing widgets are ignored (designers sometimes rename/remove dots).
    """
    w = root.findChild(QWidget, object_name)
    if w is None:
        return
    set_state_property(w, state, prop=prop)
