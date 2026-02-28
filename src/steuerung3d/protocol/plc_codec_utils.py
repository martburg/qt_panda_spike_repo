from __future__ import annotations


def to_float(s: str, default: float = 0.0) -> float:
    try:
        return float(str(s).strip())
    except Exception:
        return default


def to_int(s: str, default: int = 0) -> int:
    try:
        return int(float(str(s).strip()))
    except Exception:
        return default


def fmt(x: float) -> str:
    # Keep compact but stable formatting.
    # PLC uses LREAL/REAL parsing with '.' decimal.
    return f"{float(x):.6g}"


def bool_token(value: bool, true_token: str, false_token: str) -> str:
    return str(true_token) if bool(value) else str(false_token)
