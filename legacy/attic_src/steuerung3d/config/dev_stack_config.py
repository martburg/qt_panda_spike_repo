from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from steuerung3d.config.toml_loader import load_toml


@dataclass(frozen=True)
class AppConfig:
    dt_s: float = 0.01
    realtime: bool = True
    log_path: str = "logs/session_dev.jsonl"


@dataclass(frozen=True)
class SimConfig:
    axis_ids: List[str]


@dataclass(frozen=True)
class DevStackConfig:
    app: AppConfig
    sim: SimConfig


def load_dev_stack_config(path: Path) -> DevStackConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    raw = load_toml(path)

    app_raw = raw.get("app", {}) or {}
    app = AppConfig(
        dt_s=float(app_raw.get("dt_s", 0.01)),
        realtime=bool(app_raw.get("realtime", True)),
        log_path=str(app_raw.get("log_path", "logs/session_dev.jsonl")),
    )

    sim_raw = raw.get("sim", {}) or {}
    axis_ids = sim_raw.get("axis_ids", ["X"]) or ["X"]
    axis_ids = [str(a).strip() for a in axis_ids if str(a).strip()]

    return DevStackConfig(app=app, sim=SimConfig(axis_ids=axis_ids))
