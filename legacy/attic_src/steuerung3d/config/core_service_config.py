from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from steuerung3d.config.toml_loader import load_toml


@dataclass(frozen=True)
class AppConfig:
    dt_s: float = 0.01
    realtime: bool = True


@dataclass(frozen=True)
class CoreConfig:
    axis_ids: List[str]
    ticks: int = 500


@dataclass(frozen=True)
class CoreServiceConfig:
    app: AppConfig
    core: CoreConfig


def load_core_service_config(path: Path) -> CoreServiceConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    raw = load_toml(path)

    app_raw = raw.get("app", {}) or {}
    app = AppConfig(
        dt_s=float(app_raw.get("dt_s", 0.01)),
        realtime=bool(app_raw.get("realtime", True)),
    )

    core_raw = raw.get("core", {}) or {}
    axis_ids = core_raw.get("axis_ids", ["X"]) or ["X"]
    axis_ids = [str(a).strip() for a in axis_ids if str(a).strip()]
    ticks = int(core_raw.get("ticks", 500))

    return CoreServiceConfig(app=app, core=CoreConfig(axis_ids=axis_ids, ticks=ticks))
