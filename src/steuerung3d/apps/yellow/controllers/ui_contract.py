# src/steuerung3d/apps/yellow/controllers/ui_contract.py
"""UI contract helpers for Yellow controllers.

We have multiple .ui variants in the wild. Some widgets are optional or may have
legacy typos in their objectName. Controllers should stay resilient, but it is
still useful (especially in production) to know when a UI variant is missing
widgets we expect.

These helpers are intentionally *non-fatal*: they only log at DEBUG level.
"""

from __future__ import annotations

from typing import Iterable

from PySide6.QtWidgets import QWidget

from .widget_cache import WidgetCache



_LOGGED_CONTEXTS: set[str] = set()


def missing_optional(cache: WidgetCache, specs: Iterable[tuple[type[QWidget], str]]) -> list[str]:
    """Return a list of missing objectNames for the given specs."""
    out: list[str] = []
    for cls, name in specs:
        if not name:
            continue
        if cache.get(cls, name) is None:
            out.append(str(name))
    return out


def log_missing_optional_once(
    logger,
    cache: WidgetCache,
    specs: Iterable[tuple[type[QWidget], str]],
    *,
    context: str,
) -> None:
    """Same as log_missing_optional, but log at most once per process+context."""
    try:
        key = str(context)
        if key in _LOGGED_CONTEXTS:
            return
        _LOGGED_CONTEXTS.add(key)
        log_missing_optional(logger, cache, specs, context=context)
    except Exception:
        return


def log_missing_optional(
    logger,
    cache: WidgetCache,
    specs: Iterable[tuple[type[QWidget], str]],
    *,
    context: str,
) -> None:
    """Log missing widgets at DEBUG level.

    `specs` is a list of (class, objectName) pairs.
    """
    try:
        missing: list[str] = []
        for cls, name in specs:
            if not name:
                continue
            if cache.get(cls, name) is None:
                missing.append(str(name))
        if missing:
            logger.debug("UI contract (%s): missing optional widgets: %s", context, ", ".join(missing))
    except Exception:
        return
