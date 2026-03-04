"""Backward compatible import path for axis id normalization.

Single truth lives in :mod:`steuerung3d.core.axis_id`.
"""

from __future__ import annotations

from steuerung3d.core.axis_id import normalize_axis_id

__all__ = ["normalize_axis_id"]
