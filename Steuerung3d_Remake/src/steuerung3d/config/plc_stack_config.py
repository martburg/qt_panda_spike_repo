from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class AppConfig:
    dt_s: float = 0.01
    log_path: str = "logs/session_plc.jsonl"
    realtime: bool = True


@dataclass(frozen=True)
class PlcUdpConfig:
    bind_host: str = "0.0.0.0"
    bind_port: int = 50002
    target_host: str = "127.0.0.1"
    target_port: int = 50001

    axis_ids: List[str] = None  # filled in loader if None

    delimiter: str = ";"
    encoding: str = "ascii"
    float_fmt: str = "{:.6f}"
    true_token: str = "1"
    false_token: str = "0"


@dataclass(frozen=True)
class PlcStackConfig:
    app: AppConfig
    plc_udp: PlcUdpConfig


def load_plc_stack_config(path: Path) -> PlcStackConfig:
    """
    Loads configs/plc_stack.toml.

    Uses:
      - tomllib (stdlib) on Python >= 3.11
      - tomli fallback if installed (older Pythons)
    """
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    raw = _load_toml(path)

    app_raw = raw.get("app", {}) or {}
    plc_raw = raw.get("plc_udp", {}) or {}

    app = AppConfig(
        dt_s=float(app_raw.get("dt_s", 0.01)),
        log_path=str(app_raw.get("log_path", "logs/session_plc.jsonl")),
        realtime=bool(app_raw.get("realtime", True)),
    )

    axis_ids = plc_raw.get("axis_ids", None)
    if axis_ids is None:
        axis_ids = ["X"]
    axis_ids = [str(a) for a in axis_ids if str(a).strip()]

    plc = PlcUdpConfig(
        bind_host=str(plc_raw.get("bind_host", "0.0.0.0")),
        bind_port=int(plc_raw.get("bind_port", 50002)),
        target_host=str(plc_raw.get("target_host", "127.0.0.1")),
        target_port=int(plc_raw.get("target_port", 50001)),
        axis_ids=axis_ids,
        delimiter=str(plc_raw.get("delimiter", ";")),
        encoding=str(plc_raw.get("encoding", "ascii")),
        float_fmt=str(plc_raw.get("float_fmt", "{:.6f}")),
        true_token=str(plc_raw.get("true_token", "1")),
        false_token=str(plc_raw.get("false_token", "0")),
    )

    return PlcStackConfig(app=app, plc_udp=plc)


def _load_toml(path: Path) -> dict:
    try:
        import tomllib  # py>=3.11
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except ModuleNotFoundError:
        # optional fallback for older python
        import tomli
        return tomli.loads(path.read_text(encoding="utf-8"))
