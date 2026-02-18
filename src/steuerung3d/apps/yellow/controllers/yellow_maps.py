"""Shim: re-export Qt-free widget maps from domain."""

from __future__ import annotations

from ..domain.yellow_maps import LIMIT_WIDGETS, PARAM_WIDGETS

__all__ = [
    "PARAM_WIDGETS",
    "LIMIT_WIDGETS",
]