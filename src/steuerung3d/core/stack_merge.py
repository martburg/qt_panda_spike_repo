from __future__ import annotations

from typing import Any, Iterable


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base.

    Rules:
    - dict + dict => merge keys recursively
    - everything else (including lists) => override replaces base
    """
    out = dict(base)
    for k, v in (override or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def set_by_path(root: dict, dotted: str, value: Any) -> None:
    parts = [p for p in (dotted or "").split(".") if p]
    if not parts:
        raise ValueError("empty --set key")
    cur = root
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def apply_sets(data: dict, sets: Iterable[str], *, parse_value: callable) -> dict:
    out = dict(data)
    for item in sets or []:
        if "=" not in item:
            raise ValueError(f"Invalid --set (expected key=value): {item}")
        key, val_s = item.split("=", 1)
        set_by_path(out, key.strip(), parse_value(val_s.strip()))
    return out
