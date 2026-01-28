from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def load_toml(path: Path) -> Dict[str, Any]:
    """Load TOML from *path* using stdlib tomllib (Py>=3.11) or tomli fallback."""
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib  # type: ignore

        return tomllib.loads(text)
    except ModuleNotFoundError:
        import tomli  # type: ignore

        return tomli.loads(text)
