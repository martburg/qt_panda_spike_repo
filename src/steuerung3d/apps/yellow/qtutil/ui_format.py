"""UI formatting helpers for locale-specific display (Qt-free).

Thin re-export adapter for the canonical helpers in domain/ui_format.py.
"""

from __future__ import annotations

from ..domain.ui_format import fmt_f_unit_de, fmt_float_de

__all__ = ["fmt_float_de", "fmt_f_unit_de"]
