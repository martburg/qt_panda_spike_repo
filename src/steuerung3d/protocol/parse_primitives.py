"""Primitive parsing helpers for PLC-ish text protocols.

We intentionally centralize these so that all adapters agree on token
semantics (especially for booleans).

Accepted boolean tokens (case-insensitive):
  True-ish:  "1", "true", "t", "yes", "y", "on"
  False-ish: "0", "false", "f", "no", "n", "off"

Everything else falls back to the provided default.
"""

from __future__ import annotations


def parse_int(v: object, default: int = 0) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return int(default)


def parse_float(v: object, default: float = 0.0) -> float:
    try:
        return float(str(v).strip())
    except Exception:
        return float(default)


def parse_bool(v: object, default: bool = False) -> bool:
    if v is None:
        return bool(default)
    s = str(v).strip().lower()
    if s in ("1", "true", "t", "yes", "y", "on"):
        return True
    if s in ("0", "false", "f", "no", "n", "off"):
        return False
    return bool(default)
