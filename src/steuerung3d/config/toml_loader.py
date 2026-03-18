from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypeAlias, cast

TomlTable: TypeAlias = dict[str, object]


def _coerce_table(value: object) -> TomlTable:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(k): v for k, v in mapping.items()}


def load_toml(path: Path) -> TomlTable:
    """Load TOML from *path* using stdlib tomllib (Py>=3.11) or tomli fallback."""
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib

        data: Any = tomllib.loads(text)
    except ModuleNotFoundError:
        import tomli

        data = tomli.loads(text)
    return _coerce_table(data)
