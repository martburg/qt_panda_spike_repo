from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib  # py3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore


def parse_toml_value(s: str) -> Any:
    """Parse a TOML literal value from a CLI string.

    Examples:
      true, 123, 1.2, "text", ['a','b'] (TOML arrays use double quotes)

    If parsing fails, falls back to the raw string.
    """
    if tomllib is None:  # pragma: no cover
        return s
    try:
        return tomllib.loads(f"v = {s}")["v"]
    except Exception:
        return s


def load_toml(path: Path) -> dict:
    if tomllib is None:  # pragma: no cover
        raise RuntimeError("tomllib not available (requires Python 3.11+)")
    return tomllib.loads(Path(path).read_text(encoding="utf-8"))
