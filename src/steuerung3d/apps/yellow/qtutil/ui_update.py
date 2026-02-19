# src/steuerung3d/apps/yellow/controllers/ui_update.py
"""Small, pragmatic UI write helpers.

Goals:
- Keep controllers readable (no repeated setText / repolish boilerplate).
- Reduce UI churn: only repaint when a value actually changes.
- Stay resilient: a single widget failing to update must not crash the controller.
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QWidget


def _repolish(widget: "QWidget") -> None:
    """Force QSS to re-evaluate dynamic properties on a widget."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_state_property(widget: "QWidget", state: Any, prop: str = "state") -> None:
    """Set a QSS-driving dynamic property and repolish (only if it changed)."""
    try:
        if widget.property(prop) == state:
            return
        widget.setProperty(prop, state)
        _repolish(widget)
    except Exception:
        return


def set_state_by_object_name(root: "QWidget", object_name: str, state: Any, prop: str = "state") -> None:
    """Find a child widget under `root` by objectName and set its state property."""
    try:
        # Import only for runtime (keeps helper importable in headless/unit test contexts).
        from PySide6.QtWidgets import QWidget  # type: ignore

        w = root.findChild(QWidget, object_name)
        if w is None:
            return
        set_state_property(w, state, prop=prop)
    except Exception:
        return


def set_text(widget: Optional[Any], text: str) -> None:
    """Set QLabel/QLineEdit text only if it differs."""
    if widget is None:
        return
    try:
        cur = widget.text()  # type: ignore[attr-defined]
        if cur == text:
            return
        widget.setText(text)  # type: ignore[attr-defined]
    except Exception:
        return


def set_enabled(widget: Optional[Any], enabled: bool) -> None:
    """Set QWidget enabled state only if it differs."""
    if widget is None:
        return
    try:
        cur = bool(widget.isEnabled())  # type: ignore[attr-defined]
        en = bool(enabled)
        if cur == en:
            return
        widget.setEnabled(en)  # type: ignore[attr-defined]
    except Exception:
        return


def set_enabled_repolish(widget: Optional[Any], enabled: bool) -> None:
    """Set enabled state and repolish the widget, but only on change.

    Some Yellow UI variants rely on QSS rules that combine dynamic properties
    (e.g. paramField) with enabled/disabled state. Qt will usually restyle
    correctly on enable changes, but repolishing here is a cheap, safe guard.
    """
    if widget is None:
        return
    try:
        cur = bool(widget.isEnabled())  # type: ignore[attr-defined]
        en = bool(enabled)
        if cur == en:
            return
        widget.setEnabled(en)  # type: ignore[attr-defined]
        # Repolish is intentionally only done when enabled state changed.
        try:
            _repolish(widget)  # type: ignore[arg-type]
        except Exception:
            pass
    except Exception:
        return


def set_checked(widget: Optional[Any], checked: bool, *, block_signals: bool = False) -> None:
    """Set QAbstractButton/QCheckBox checked state only if it differs.

    If block_signals=True, the widget's signals are temporarily blocked.
    """
    if widget is None:
        return
    try:
        v = bool(checked)
        if bool(widget.isChecked()) == v:  # type: ignore[attr-defined]
            return
        if block_signals:
            try:
                was = widget.blockSignals(True)  # type: ignore[attr-defined]
            except Exception:
                was = None
            widget.setChecked(v)  # type: ignore[attr-defined]
            if was is not None:
                try:
                    widget.blockSignals(was)  # type: ignore[attr-defined]
                except Exception:
                    pass
        else:
            widget.setChecked(v)  # type: ignore[attr-defined]
    except Exception:
        return


def update_slider(
    slider: Optional[Any],
    *,
    minimum: int | None = None,
    maximum: int | None = None,
    value: int | None = None,
    block_signals: bool = True,
) -> None:
    """Update a QAbstractSlider's min/max/value with minimal churn.

    All arguments are optional. When provided, the corresponding property is only
    written if it differs. If block_signals=True, the slider's signals are
    blocked while applying updates.
    """
    if slider is None:
        return
    try:
        need_min = minimum is not None and int(slider.minimum()) != int(minimum)  # type: ignore[attr-defined]
        need_max = maximum is not None and int(slider.maximum()) != int(maximum)  # type: ignore[attr-defined]
        need_val = value is not None and int(slider.value()) != int(value)  # type: ignore[attr-defined]
        if not (need_min or need_max or need_val):
            return

        if block_signals:
            try:
                was = slider.blockSignals(True)  # type: ignore[attr-defined]
            except Exception:
                was = None
        else:
            was = None

        # Range first, then value.
        if need_min:
            slider.setMinimum(int(minimum))  # type: ignore[attr-defined]
        if need_max:
            slider.setMaximum(int(maximum))  # type: ignore[attr-defined]
        if need_val:
            slider.setValue(int(value))  # type: ignore[attr-defined]

        if was is not None:
            try:
                slider.blockSignals(was)  # type: ignore[attr-defined]
            except Exception:
                pass
    except Exception:
        return
