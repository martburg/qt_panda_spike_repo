"""Public seam for DenSi engine.

This file stays small and stable for imports.
Implementation lives in :mod:`engine_core`.

Note: Splitting is structural only (Lane 1). DenSi semantics are unchanged.
"""

from __future__ import annotations

from .engine_core import DenSiEngine

__all__ = ["DenSiEngine"]
