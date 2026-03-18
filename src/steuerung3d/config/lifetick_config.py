from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from steuerung3d.config.toml_loader import load_toml


@dataclass(frozen=True)
class LifetickTraceConfig:
    """Config for lifetick tracing ("oscilloscope" style) output.

    The intent is to optionally stream high-frequency Lifetick events into a
    dedicated rotating log file without flooding the main core logger.
    """

    enable: bool = False
    every_s: float = 0.5

    # File output. If *path* is relative, it is interpreted relative to CWD.
    path: str = ".run/lifetick.log"

    # Rotation settings.
    max_bytes: int = 2_000_000
    backup_count: int = 5


def _as_table(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): v for k, v in value.items()}


def _as_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except Exception:
            return float(default)
    return float(default)


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except Exception:
            return int(default)
    return int(default)


def load_lifetick_config(path: Path) -> LifetickTraceConfig:
    """Load lifetick trace config from TOML.

    Missing file -> defaults.
    Invalid fields -> best-effort defaults.
    """

    if not path.exists():
        return LifetickTraceConfig()

    data = load_toml(path)
    root = _as_table(data.get("lifetick", {}))
    if not root:
        return LifetickTraceConfig()

    def _get_bool(key: str, default: bool) -> bool:
        return bool(root.get(key, default))

    def _get_float(key: str, default: float) -> float:
        return _as_float(root.get(key, default), default)

    def _get_int(key: str, default: int) -> int:
        return _as_int(root.get(key, default), default)

    def _get_str(key: str, default: str) -> str:
        v = root.get(key, default)
        return str(v) if v is not None else str(default)

    every_s = max(0.0, _get_float("every_s", LifetickTraceConfig.every_s))
    max_bytes = max(1, _get_int("max_bytes", LifetickTraceConfig.max_bytes))
    backup_count = max(0, _get_int("backup_count", LifetickTraceConfig.backup_count))

    return LifetickTraceConfig(
        enable=_get_bool("enable", LifetickTraceConfig.enable),
        every_s=every_s,
        path=_get_str("path", LifetickTraceConfig.path),
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
