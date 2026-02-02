"""Tiny logging helper to make multi-process stacks debuggable.

We frequently run many Python processes at once (Core, Core-UDP, multiple HiPs,
multiple DenSi instances, inputd/joy2intent, ...). When all of them log to a
shared console (or to files later), we need each log line to carry *identity*.

This module installs a LogRecordFactory that adds two attributes to every
LogRecord:

  - role: short process role name (e.g. "HiP", "CoreUDP")
  - axis: optional axis id (e.g. "Anton")

Both default from environment variables:

  ST3D_ROLE, ST3D_AXIS

If you don't set them, we fall back to sensible defaults.
"""

from __future__ import annotations

import logging
import os
from typing import Callable


def install_log_context(*, role: str | None = None, axis: str | None = None) -> None:
    """Attach role/axis identity to all subsequent log records."""

    role_s = (role or os.getenv("ST3D_ROLE") or "app").strip() or "app"
    axis_s = (axis if axis is not None else os.getenv("ST3D_AXIS") or "-").strip() or "-"

    base_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        record = base_factory(*args, **kwargs)
        # These names must match the Formatter keys used in apps.
        record.role = role_s
        record.axis = axis_s
        return record

    # Avoid wrapping multiple times if called again.
    # (This keeps it predictable if a module imports+installs twice.)
    current = logging.getLogRecordFactory()
    if current is not record_factory:
        logging.setLogRecordFactory(record_factory)


def child_env(*, role: str, axis: str | None = None) -> dict[str, str]:
    """Convenience: build an env dict for subprocess children."""

    env = os.environ.copy()
    env["ST3D_ROLE"] = str(role)
    if axis is not None:
        env["ST3D_AXIS"] = str(axis)
    return env
