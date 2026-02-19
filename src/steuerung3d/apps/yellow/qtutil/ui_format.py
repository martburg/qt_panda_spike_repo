"""UI formatting helpers for locale-specific display (Qt-free)."""

from __future__ import annotations

from typing import Any

from ..domain.ui_format import fmt_f_unit


def fmt_float_de(v: Any, *, ndigits: int = 2, unit: str | None = None, empty: str = "") -> str:
    try:
        s = f"{float(v):0.{int(ndigits)}f}"
    except Exception:
        return str(empty)
    if unit:
        s = f"{s} {unit}"
    return s.replace(".", ",")


def fmt_f_unit_de(v: Any, *, unit: str, ndigits: int = 2, empty: str = "--") -> str:
    s = fmt_f_unit(v, unit, ndigits=ndigits, empty=empty)
    return str(s).replace(".", ",")
