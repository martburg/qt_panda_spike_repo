# src/steuerung3d/apps/yellow/qtutil/ui_panel_state.py
"""Shared helpers for common panel state transitions.

Yellow UIs have a few recurring "panel mode" transitions, e.g. Hip pooled panels
switch between unattached (dead/grey) and attached (live) states.

These helpers keep that logic small and consistent across controllers while
preserving semantics: they are best-effort and never raise.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

from PySide6.QtWidgets import QCheckBox, QLineEdit, QWidget

from .ui_update import set_checked, set_enabled, set_text


def clear_line_edits(
    root: QWidget, *, keep: Optional[Iterable[QLineEdit]] = None, text: str = ""
) -> None:
    """Set text on all QLineEdit descendants of root, except those in `keep`."""
    try:
        keep_set = set(keep or [])
        for le in root.findChildren(QLineEdit):
            if le in keep_set:
                continue
            set_text(le, text)
    except Exception:
        return


def set_enabled_many(widgets: Iterable[Any], enabled: bool) -> None:
    """Enable/disable a list of widgets (best effort)."""
    for w in widgets:
        set_enabled(w, enabled)


def neutralize_dots(set_dot: Callable[[str, Any], None], dot_names: Iterable[str]) -> None:
    """Set a group of dot widgets to the neutral/unknown state (None)."""
    for n in dot_names:
        if n:
            set_dot(n, None)


def uncheck_checkboxes(checkboxes: Iterable[QCheckBox]) -> None:
    """Clear a group of checkboxes without throwing."""
    for cb in checkboxes:
        set_checked(cb, False)
