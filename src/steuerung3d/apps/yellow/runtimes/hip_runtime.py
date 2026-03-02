from __future__ import annotations

"""Qt-free runtime seam for HiP (public entry points).

This module intentionally stays small.
Implementation details live in :mod:`steuerung3d.apps.yellow.runtimes.hip_runtime_impl`.

Lane 1 refactor: no semantic changes; public imports stay stable.
"""

from steuerung3d.apps.yellow.runtimes.hip_runtime_impl import (
    HipRuntime,
    HipRuntimeInputs,
    HipRuntimeResult,
)

__all__ = ["HipRuntime", "HipRuntimeInputs", "HipRuntimeResult"]
