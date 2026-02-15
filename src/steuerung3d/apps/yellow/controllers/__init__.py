"""Yellow UI controller helpers.

This package contains both Qt-dependent controller/bindings code and pure helper
modules (e.g. UI state mapping, E-Stop decoding helpers).

To keep pure helpers importable in headless environments (CI, codec tooling),
we avoid importing any Qt modules at package import time.

If you want controllers, import them directly:
  - from ...hip_controller import HiPController
  - from ...densi_controller import DenSiController
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING


__all__ = ["YellowBindings", "IntentOut", "TelemetryIn", "CommandIn", "TelemetryOut"]


if TYPE_CHECKING:  # pragma: no cover
    # For typing only; runtime access is provided via __getattr__.
    from .bindings import YellowBindings
    from .ports import CommandIn, IntentOut, TelemetryIn, TelemetryOut


def __getattr__(name: str):  # pragma: no cover
    """Lazy exports for convenience imports.

    This lets callers do:
        from steuerung3d.apps.yellow.controllers import YellowBindings

    without importing PySide6 unless the symbol is actually accessed.
    """

    if name == "YellowBindings":
        return import_module(".bindings", __name__).YellowBindings
    if name in {"CommandIn", "IntentOut", "TelemetryIn", "TelemetryOut"}:
        return getattr(import_module(".ports", __name__), name)
    raise AttributeError(name)
