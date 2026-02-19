# src/steuerung3d/apps/yellow/qtutil/ui_contract.py
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


_LOGGED_REQUIRED_CONTEXTS: set[str] = set()


def missing_required(cache: WidgetCache, specs: Iterable[tuple[type[QWidget], str]]) -> list[str]:
    """Return a list of missing *required* objectNames for the given specs."""
    # Implementation is the same as missing_optional; intent differs.
    return missing_optional(cache, specs)


def log_missing_required_once(
    logger,
    cache: WidgetCache,
    specs: Iterable[tuple[type[QWidget], str]],
    *,
    context: str,
) -> None:
    """Log missing required widgets at most once per process+context (WARNING)."""
    try:
        key = str(context)
        if key in _LOGGED_REQUIRED_CONTEXTS:
            return
        _LOGGED_REQUIRED_CONTEXTS.add(key)
        log_missing_required(logger, cache, specs, context=context)
    except Exception:
        return


def log_missing_required(
    logger,
    cache: WidgetCache,
    specs: Iterable[tuple[type[QWidget], str]],
    *,
    context: str,
) -> None:
    """Log missing required widgets at WARNING level.

    Required widgets are those that the controller expects to exist for safe operation.
    We still keep this non-fatal because some deployments use partial UIs.
    """
    try:
        missing = missing_optional(cache, specs)
        if missing:
            logger.warning("UI contract (%s): missing REQUIRED widgets: %s", context, ", ".join(missing))
    except Exception:
        return


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
