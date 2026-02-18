"""Shim: re-export Qt-free formatting helpers from domain."""

from __future__ import annotations

from ..domain.ui_format import (
    fmt_f,
    fmt_f_unit,
    fmt_i,
    fmt_i_unit,
)

__all__ = [
    "fmt_f",
    "fmt_f_unit",
    "fmt_i",
    "fmt_i_unit",
]