from __future__ import annotations

import logging

from steuerung3d.util.log_context import install_log_context


def bootstrap_logging(
    *,
    role: str,
    log_level: str = "info",
    axis: str = "",
    fmt: str = "%(asctime)s %(levelname)s %(name)s: %(message)s",
) -> None:
    """Standard logging + log-context bootstrap for app entrypoints.

    This is intentionally tiny and dependency-free so every __main__.py can
    share the same behavior.

    Args:
        role: Log context role (e.g. "core", "hi_p", "den_si").
        log_level: One of debug/info/warning/error (case-insensitive).
        axis: Optional axis id for context.
        fmt: logging.basicConfig format string.
    """

    lvl_name = str(log_level or "info").upper()
    level = getattr(logging, lvl_name, logging.INFO)

    logging.basicConfig(level=level, format=fmt)
    install_log_context(role=str(role), axis=str(axis or ""))
