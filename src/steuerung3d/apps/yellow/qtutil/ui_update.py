"""Small, pragmatic UI write helpers.

Goals:
- Keep controllers readable (no repeated setText / repolish boilerplate).
- Reduce UI churn: only repaint when a value actually changes.
- Stay resilient: a single widget failing to update must not crash the controller.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QWidget


@runtime_checkable
class _StyleLike(Protocol):
    def unpolish(self, widget: object) -> None: ...
    def polish(self, widget: object) -> None: ...


@runtime_checkable
class _WidgetLike(Protocol):
    def style(self) -> _StyleLike: ...
    def update(self) -> None: ...
    def property(self, name: str) -> object: ...
    def setProperty(self, name: str, value: object) -> bool: ...


@runtime_checkable
class _HasText(Protocol):
    def text(self) -> str: ...
    def setText(self, text: str) -> None: ...


@runtime_checkable
class _HasEnabled(Protocol):
    def isEnabled(self) -> bool: ...
    def setEnabled(self, enabled: bool) -> None: ...


@runtime_checkable
class _HasChecked(Protocol):
    def isChecked(self) -> bool: ...
    def setChecked(self, checked: bool) -> None: ...


@runtime_checkable
class _HasBlockSignals(Protocol):
    def blockSignals(self, block: bool) -> bool: ...


@runtime_checkable
class _SliderLike(Protocol):
    def minimum(self) -> int: ...
    def maximum(self) -> int: ...
    def value(self) -> int: ...
    def setMinimum(self, value: int) -> None: ...
    def setMaximum(self, value: int) -> None: ...
    def setValue(self, value: int) -> None: ...
    def blockSignals(self, block: bool) -> bool: ...


def _repolish(widget: object) -> None:
    """Force QSS to re-evaluate dynamic properties on a widget."""
    if not isinstance(widget, _WidgetLike):
        return
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


@contextmanager
def blocked_signals(widget: object, *, enabled: bool = True) -> Iterator[None]:
    """Best-effort signal blocker for Qt widgets.

    This intentionally stays tolerant: widgets without blockSignals support, or
    widgets that raise while blocking/restoring, are treated as no-ops.
    """
    if not enabled or widget is None or not isinstance(widget, _HasBlockSignals):
        yield
        return

    was: bool | None
    try:
        was = widget.blockSignals(True)
    except Exception:
        was = None

    try:
        yield
    finally:
        if was is not None:
            try:
                widget.blockSignals(was)
            except Exception:
                pass


def set_state_property(widget: object, state: Any, prop: str = "state") -> None:
    """Set a QSS-driving dynamic property and repolish (only if it changed)."""
    if not isinstance(widget, _WidgetLike):
        return
    try:
        if widget.property(prop) == state:
            return
        widget.setProperty(prop, state)
        _repolish(widget)
    except Exception:
        return


def set_state_by_object_name(
    root: "QWidget", object_name: str, state: Any, prop: str = "state"
) -> None:
    """Find a child widget under `root` by objectName and set its state property."""
    try:
        # Import only for runtime (keeps helper importable in headless/unit test contexts).
        from PySide6.QtWidgets import QWidget

        w = root.findChild(QWidget, object_name)
        if w is None:
            return
        set_state_property(w, state, prop=prop)
    except Exception:
        return


def set_text(widget: Optional[_HasText], text: str) -> None:
    """Set QLabel/QLineEdit text only if it differs."""
    if widget is None:
        return
    try:
        if widget.text() == text:
            return
        widget.setText(text)
    except Exception:
        return


def set_enabled(widget: Optional[_HasEnabled], enabled: bool) -> None:
    """Set QWidget enabled state only if it differs."""
    if widget is None:
        return
    try:
        en = bool(enabled)
        if bool(widget.isEnabled()) == en:
            return
        widget.setEnabled(en)
    except Exception:
        return


def set_enabled_repolish(widget: Optional[_HasEnabled], enabled: bool) -> None:
    """Set enabled state and repolish the widget, but only on change.

    Some Yellow UI variants rely on QSS rules that combine dynamic properties
    (e.g. paramField) with enabled/disabled state. Qt will usually restyle
    correctly on enable changes, but repolishing here is a cheap, safe guard.
    """
    if widget is None:
        return
    try:
        en = bool(enabled)
        if bool(widget.isEnabled()) == en:
            return
        widget.setEnabled(en)
        # Repolish is intentionally only done when enabled state changed.
        try:
            _repolish(widget)
        except Exception:
            pass
    except Exception:
        return


def set_checked(
    widget: Optional[_HasChecked], checked: bool, *, block_signals: bool = False
) -> None:
    """Set QAbstractButton/QCheckBox checked state only if it differs.

    If block_signals=True, the widget's signals are temporarily blocked.
    """
    if widget is None:
        return
    try:
        v = bool(checked)
        if bool(widget.isChecked()) == v:
            return
        with blocked_signals(widget, enabled=block_signals):
            widget.setChecked(v)
    except Exception:
        return


def update_slider(
    slider: Optional[_SliderLike],
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
        need_min = minimum is not None and int(slider.minimum()) != int(minimum)
        need_max = maximum is not None and int(slider.maximum()) != int(maximum)
        need_val = value is not None and int(slider.value()) != int(value)
        if not (need_min or need_max or need_val):
            return

        # Range first, then value.
        with blocked_signals(slider, enabled=block_signals):
            if need_min and minimum is not None:
                slider.setMinimum(int(minimum))
            if need_max and maximum is not None:
                slider.setMaximum(int(maximum))
            if need_val and value is not None:
                slider.setValue(int(value))
    except Exception:
        return
