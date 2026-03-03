"""Deprecated axis id helpers.

Use `steuerung3d.core.axis_ids.normalize_axis_id` as the single source of truth.

This module is kept temporarily to avoid import churn during refactors.
"""

from __future__ import annotations

from steuerung3d.core.axis_ids import normalize_axis_id

__all__ = ["normalize_axis_id"]
