from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, TypeAlias, cast

TomlTable: TypeAlias = dict[str, object]


class _TomlModule(Protocol):
    def loads(self, s: str, /) -> object: ...


def _coerce_table(value: object) -> TomlTable:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(k): v for k, v in mapping.items()}


def load_toml(path: Path) -> TomlTable:
    """Load TOML from *path* using stdlib tomllib (Py>=3.11) or tomli fallback."""
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib as _toml_module
    except ModuleNotFoundError:
        import tomli as _toml_module

    data = cast(_TomlModule, _toml_module).loads(text)
    return _coerce_table(data)
