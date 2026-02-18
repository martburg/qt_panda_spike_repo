"""Backward-compatible import path for HipQtBinder.

This module now delegates to the binder implementation under
apps/yellow/binders.
"""

from __future__ import annotations

from ..binders.hip_qt_binder import HipQtBinder, HipUiInputs

__all__ = ["HipQtBinder", "HipUiInputs"]
