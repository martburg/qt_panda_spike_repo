# src/steuerung3d/apps/yellow/domain/ui_format.py
"""Formatting helpers for UI readouts.

We keep formatting logic centralized so controller code reads like a spec and
remains consistent across HiP and DenSi.
"""

from __future__ import annotations

from typing import Any


def fmt_f(x: Any, ndigits: int = 3, empty: str = "--") -> str:
    """Format a float-like value or return `empty` if None/invalid."""
    if x is None:
        return empty
    try:
        return f"{float(x):.{ndigits}f}"
    except Exception:
        return empty


def fmt_f_unit(x: Any, unit: str, ndigits: int = 2, empty: str = "--") -> str:
    """Format float + unit, e.g. '1.23 m'."""
    s = fmt_f(x, ndigits=ndigits, empty="")
    return f"{s} {unit}" if s else empty


def fmt_i_unit(x: Any, unit: str, empty: str = "--") -> str:
    """Format int + unit, e.g. '12 A'."""
    s = fmt_i(x, empty="")
    return f"{s} {unit}" if s else empty


def fmt_i(x: Any, empty: str = "--") -> str:
    """Format an int-like value or return `empty` if None/invalid."""
    if x is None:
        return empty
    try:
        return str(int(x))
    except Exception:
        return empty


def fmt_float_de(v: Any, *, ndigits: int = 2, unit: str | None = None, empty: str = "") -> str:
    """Format a float with comma decimal separator and optional unit."""
    try:
        s = f"{float(v):0.{int(ndigits)}f}"
    except Exception:
        return str(empty)
    if unit:
        s = f"{s} {unit}"
    return s.replace(".", ",")


def fmt_f_unit_de(v: Any, *, unit: str, ndigits: int = 2, empty: str = "--") -> str:
    """Format float + unit with comma decimal separator."""
    s = fmt_f_unit(v, unit, ndigits=ndigits, empty=empty)
    return str(s).replace(".", ",")
