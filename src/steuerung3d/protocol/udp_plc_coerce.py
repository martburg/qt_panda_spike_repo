"""Tolerant primitive coercion for legacy UDP PLC channels.

Split out of :mod:`steuerung3d.protocol.udp_plc_channels` as a Lane-1 refactor
with no intended semantic changes.
"""

from __future__ import annotations

from steuerung3d.protocol.parse_primitives import parse_bool, parse_float


def to_int(x: object, default: int = 0) -> int:
    """Tolerant int conversion for PLC tokens (accepts '1', '1.0', etc.)."""
    try:
        return int(float(str(x).strip()))
    except Exception:
        return int(default)


def to_float(x: object, default: float = 0.0) -> float:
    """Tolerant float conversion for PLC tokens."""
    return float(parse_float(x, default=default))


def to_bool_token(x: object, default: bool = False) -> bool:
    """Parse legacy PLC-ish booleans.

    ST truth (KommAnton__MAIN.st):
      - `Intent` is compared against the *string* 'True' (case-sensitive).
      - Other on-wire flags are typically numeric (WORD/INT/DWORD) where non-zero means true.

    Policy here:
      - empty token => False (even if default=True) (matches previous behavior)
      - accept a broad token set (true/false/on/off/1/0/...) via :func:`parse_bool`
      - accept numeric-ish tokens as well (e.g. DWORD bitfields): non-zero => True
    """
    try:
        s = str(x).strip()
    except Exception:
        return bool(default)
    if s == "":
        return False

    sl = s.lower()

    # First accept the centralized token set (1/0, true/false, on/off, ...).
    v = parse_bool(s, default=default)
    if sl in ("1", "0", "true", "false", "t", "f", "yes", "no", "y", "n", "on", "off"):
        return bool(v)

    # Then accept legacy numeric-ish tokens as well (e.g. DWORD bitfields): non-zero => True.
    try:
        return int(sl, 10) != 0
    except Exception:
        try:
            return float(sl) != 0.0
        except Exception:
            return bool(default)
