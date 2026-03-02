"""Axis id normalization helpers.

Lane 1 note:
- This module is intentionally side-effect free.
- Introducing the helpers is a structural cleanup; usage should be applied only at
  I/O boundaries where case/whitespace variations are already accepted implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AxisId:
    canonical: str


def normalize_axis_id(raw: str) -> str:
    """Normalize an axis id token coming from UI/CLI/wire.

    - trims whitespace
    - collapses internal whitespace
    - preserves existing canonical casing for known ids

    This function is intentionally conservative: it only canonicalizes a small
    known set. Unknown ids are returned in stripped form.
    """

    s = " ".join(raw.strip().split())
    if not s:
        return ""

    # Canonical IDs used across the repo.
    # Keep the set small and explicit to avoid surprising changes.
    known = {
        "anton": "Anton",
        "burt": "Burt",
        "cecil": "Cecil",
        "debby": "Debby",
    }
    return known.get(s.casefold(), s)
