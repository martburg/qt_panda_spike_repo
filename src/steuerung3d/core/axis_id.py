"""Axis id normalization (single truth).

Goal: accept tolerant inputs from UI/HiP (e.g. "ANTON", " ANton ") while keeping
core-internal dict keys stable.

Policy:
- Strip whitespace.
- For purely alphabetic ids, canonicalize to "Anton" (first letter upper, rest lower).
- For mixed tokens (digits, underscores, etc.), keep case as-is after stripping.

This is intentionally conservative to avoid surprising transformations for
non-axis identifiers.
"""

from __future__ import annotations


def normalize_axis_id(axis_id: object) -> str:
    s = str(axis_id or "").strip()
    if not s:
        return ""
    if s.isalpha():
        return s[0].upper() + s[1:].lower()
    return s
