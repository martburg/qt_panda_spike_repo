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
class ClientConfig:
    axis_ids: List[str]


@dataclass(frozen=True)
class CliClientConfig:
    app: AppConfig
    client: ClientConfig


def load_cli_client_config(path: Path) -> CliClientConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    raw = load_toml(path)

    app_raw = raw.get("app", {}) or {}
    app = AppConfig(
        dt_s=float(app_raw.get("dt_s", 0.01)),
        realtime=bool(app_raw.get("realtime", True)),
    )

    client_raw = raw.get("client", {}) or {}
    axis_ids = client_raw.get("axis_ids", ["X"]) or ["X"]
    axis_ids = [str(a).strip() for a in axis_ids if str(a).strip()]

    return CliClientConfig(app=app, client=ClientConfig(axis_ids=axis_ids))
