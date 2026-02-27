from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from steuerung3d.config.toml_loader import load_toml


@dataclass(frozen=True)
class LifrtickTraceConfig:
    """Config for lifetick tracing ("oscilloscope" style) output.

    The intent is to optionally stream high-frequency Lifetick events into a
    dedicated rotating log file without flooding the main core logger.
    """

    enable: bool = False
    every_s: float = 0.5

    # File output. If *path* is relative, it is interpreted relative to CWD.
    path: str = ".run/lifrtick.log"

    # Rotation settings.
    max_bytes: int = 2_000_000
    backup_count: int = 5


def load_lifrtick_config(path: Path) -> LifrtickTraceConfig:
    """Load lifrtick trace config from TOML.

    Missing file -> defaults.
    Invalid fields -> best-effort defaults.
    """

    if not path.exists():
        return LifrtickTraceConfig()

    data = load_toml(path)
    root = data.get("lifrtick", {}) if isinstance(data, dict) else {}
    if not isinstance(root, dict):
        return LifrtickTraceConfig()

    def _get_bool(key: str, default: bool) -> bool:
        v = root.get(key, default)
        return bool(v)

    def _get_float(key: str, default: float) -> float:
        v = root.get(key, default)
        try:
            return float(v)
        except Exception:
            return float(default)

    def _get_int(key: str, default: int) -> int:
        v = root.get(key, default)
        try:
            return int(v)
        except Exception:
            return int(default)

    def _get_str(key: str, default: str) -> str:
        v: Any = root.get(key, default)
        return str(v) if v is not None else str(default)

    every_s = max(0.0, _get_float("every_s", LifrtickTraceConfig.every_s))
    max_bytes = max(1, _get_int("max_bytes", LifrtickTraceConfig.max_bytes))
    backup_count = max(0, _get_int("backup_count", LifrtickTraceConfig.backup_count))

    return LifrtickTraceConfig(
        enable=_get_bool("enable", LifrtickTraceConfig.enable),
        every_s=every_s,
        path=_get_str("path", LifrtickTraceConfig.path),
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
