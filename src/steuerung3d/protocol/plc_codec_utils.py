from __future__ import annotations

from steuerung3d.protocol.parse_primitives import (
    parse_bool as _parse_bool,
    parse_float as _parse_float,
    parse_int as _parse_int,
)


def to_float(s: str, default: float = 0.0) -> float:
    return _parse_float(s, default=default)


def to_int(s: str, default: int = 0) -> int:
    # Legacy behavior: tolerate floats on the wire (e.g. '1.0')
    try:
        return int(float(str(s).strip()))
    except Exception:
        return int(default)


def fmt(x: float) -> str:
    # Keep compact but stable formatting.
    # PLC uses LREAL/REAL parsing with '.' decimal.
    return f"{float(x):.6g}"


def bool_token(value: bool, true_token: str, false_token: str) -> str:
    return str(true_token) if bool(value) else str(false_token)
