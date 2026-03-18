from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any, TypeAlias, cast

JsonMap: TypeAlias = dict[str, object]


def _as_map(value: object) -> JsonMap:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): v for k, v in value.items()}


def deep_merge(base: Mapping[str, object], override: Mapping[str, object]) -> JsonMap:
    """Recursively merge override into base.

    Rules:
    - dict + dict => merge keys recursively
    - everything else (including lists) => override replaces base
    """
    out: JsonMap = dict(base)
    for k, v in dict(override or {}).items():
        cur = out.get(k)
        if isinstance(cur, Mapping) and isinstance(v, Mapping):
            out[k] = deep_merge(_as_map(cur), _as_map(v))
        else:
            out[k] = v
    return out


def set_by_path(root: JsonMap, dotted: str, value: Any) -> None:
    parts = [p for p in (dotted or "").split(".") if p]
    if not parts:
        raise ValueError("empty --set key")
    cur: JsonMap = root
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            new_dict: JsonMap = {}
            cur[p] = new_dict
            nxt = new_dict
        cur = cast(JsonMap, nxt)
    cur[parts[-1]] = value


def apply_sets(
    data: Mapping[str, object],
    sets: Iterable[str],
    *,
    parse_value: Callable[[str], Any],
) -> JsonMap:
    out: JsonMap = dict(data)
    for item in sets or []:
        if "=" not in item:
            raise ValueError(f"Invalid --set (expected key=value): {item}")
        key, val_s = item.split("=", 1)
        set_by_path(out, key.strip(), parse_value(val_s.strip()))
    return out
