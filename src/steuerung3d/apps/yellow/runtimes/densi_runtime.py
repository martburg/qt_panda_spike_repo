"""Qt-free runtime seam for DenSi (public entry points).

This module intentionally stays small.
Implementation details live in :mod:`steuerung3d.apps.yellow.runtimes.densi_runtime_impl`.

Lane 1 refactor: no semantic changes; public imports stay stable.
"""

from __future__ import annotations

from steuerung3d.apps.yellow.runtimes.densi_runtime_impl import DensiRuntime, DensiRuntimeResult

__all__ = ["DensiRuntime", "DensiRuntimeResult"]
