from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypeAlias, cast

try:
    import tomllib as _tomllib  # py3.11+
except Exception:  # pragma: no cover
    _tomllib = None

tomllib = cast(Any, _tomllib)

TomlTable: TypeAlias = dict[str, object]


def _coerce_table(value: object) -> TomlTable:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): v for k, v in value.items()}


def parse_toml_value(s: str) -> Any:
    """Parse a TOML literal value from a CLI string.

    Examples:
      true, 123, 1.2, "text", ['a','b'] (TOML arrays use double quotes)

    If parsing fails, falls back to the raw string.
    """
    if tomllib is None:  # pragma: no cover
        return s
    try:
        return cast(Any, tomllib.loads(f"v = {s}"))["v"]
    except Exception:
        return s


def load_toml(path: Path) -> TomlTable:
    if tomllib is None:  # pragma: no cover
        raise RuntimeError("tomllib not available (requires Python 3.11+)")
    data: object = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return _coerce_table(data)
