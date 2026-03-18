"""Small, safe helpers for Qt binders."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Protocol

from .ui_update import set_text


class SupportsBlockSignals(Protocol):
    def blockSignals(self, block: bool) -> bool: ...


def safe_set_text(widget: object | None, text: str) -> None:
    set_text(widget, str(text))


@contextmanager
def block_signals(widget: SupportsBlockSignals | None) -> Iterator[None]:
    if widget is None:
        yield
        return
    was = widget.blockSignals(True)
    try:
        yield
    finally:
        widget.blockSignals(was)
