from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from steuerung3d.config.toml_loader import load_toml


@dataclass(frozen=True)
class AppConfig:
    dt_s: float = 0.01


@dataclass(frozen=True)
class ReplayConfig:
    eps: float = 1e-9
    compare_command_frames: bool = True


@dataclass(frozen=True)
class ReplayPlayerConfig:
    app: AppConfig
    replay: ReplayConfig


def load_replay_player_config(path: Path) -> ReplayPlayerConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    raw = load_toml(path)

    app_raw = raw.get("app", {}) or {}
    app = AppConfig(dt_s=float(app_raw.get("dt_s", 0.01)))

    rep_raw = raw.get("replay", {}) or {}
    replay = ReplayConfig(
        eps=float(rep_raw.get("eps", 1e-9)),
        compare_command_frames=bool(rep_raw.get("compare_command_frames", True)),
    )

    return ReplayPlayerConfig(app=app, replay=replay)
