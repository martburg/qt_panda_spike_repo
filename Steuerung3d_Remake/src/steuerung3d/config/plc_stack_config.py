from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


# --------------------
# Dataclasses (schema)
# --------------------

@dataclass(frozen=True)
class AppConfig:
    dt_s: float = 0.01
    realtime: bool = True
    log_path: str = "logs/session_plc.jsonl"


@dataclass(frozen=True)
class PlcEndpointConfig:
    name: str
    bind_host: str
    bind_port: int
    target_host: str
    target_port: int
    axis_ids: List[str]

    delimiter: str = ";"
    encoding: str = "ascii"
    float_fmt: str = "{:.6f}"
    true_token: str = "1"
    false_token: str = "0"


@dataclass(frozen=True)
class PlcStackConfig:
    app: AppConfig
    plc_endpoints: List[PlcEndpointConfig]


# --------------------
# Loader
# --------------------

def load_plc_stack_config(path: Path) -> PlcStackConfig:
    """Load PLC stack configuration from TOML.

    Authoritative format:
      - [app]
      - [[plc_endpoints]] (list)

    Optional back-compat:
      - [plc_udp] (legacy single-endpoint) is mapped to one endpoint.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    raw = _load_toml(path)

    app_raw = raw.get("app", {}) or {}
    app = AppConfig(
        dt_s=float(app_raw.get("dt_s", 0.01)),
        realtime=bool(app_raw.get("realtime", True)),
        log_path=str(app_raw.get("log_path", "logs/session_plc.jsonl")),
    )

    endpoints_raw = raw.get("plc_endpoints", None)

    # Back-compat: legacy single-endpoint section
    if endpoints_raw is None:
        legacy = raw.get("plc_udp", None)
        if legacy:
            endpoints_raw = [_legacy_plc_udp_to_endpoint(legacy)]
        else:
            endpoints_raw = []

    if not isinstance(endpoints_raw, list):
        raise ValueError("TOML: plc_endpoints must be a list (use [[plc_endpoints]]).")

    endpoints: List[PlcEndpointConfig] = []
    for i, e in enumerate(endpoints_raw):
        if not isinstance(e, dict):
            raise ValueError(f"TOML: plc_endpoints[{i}] must be a table")

        axis_ids = e.get("axis_ids", None)
        if axis_ids is None:
            raise ValueError(f"TOML: plc_endpoints[{i}].axis_ids is required")
        axis_ids = [str(a).strip() for a in axis_ids if str(a).strip()]

        endpoints.append(
            PlcEndpointConfig(
                name=str(e.get("name", "")).strip() or f"plc{i}",
                bind_host=str(e.get("bind_host", "0.0.0.0")),
                bind_port=int(e.get("bind_port", 0)),
                target_host=str(e.get("target_host", "")),
                target_port=int(e.get("target_port", 0)),
                axis_ids=axis_ids,
                delimiter=str(e.get("delimiter", ";")),
                encoding=str(e.get("encoding", "ascii")),
                float_fmt=str(e.get("float_fmt", "{:.6f}")),
                true_token=str(e.get("true_token", "1")),
                false_token=str(e.get("false_token", "0")),
            )
        )

    _validate(endpoints)
    return PlcStackConfig(app=app, plc_endpoints=endpoints)


def _validate(endpoints: List[PlcEndpointConfig]) -> None:
    if not endpoints:
        raise ValueError("No plc_endpoints configured. Add at least one [[plc_endpoints]] entry.")

    names = [e.name for e in endpoints]
    if len(set(names)) != len(names):
        raise ValueError(f"Duplicate plc_endpoints names: {names}")

    owned = {}
    for e in endpoints:
        if not e.axis_ids:
            raise ValueError(f"Endpoint '{e.name}' has empty axis_ids")

        if not e.target_host:
            raise ValueError(f"Endpoint '{e.name}' missing target_host")
        if e.bind_port <= 0 or e.target_port <= 0:
            raise ValueError(
                f"Endpoint '{e.name}' has invalid ports bind_port={e.bind_port} target_port={e.target_port}"
            )

        for ax in e.axis_ids:
            if ax in owned:
                raise ValueError(f"Axis '{ax}' is owned by both '{owned[ax]}' and '{e.name}'")
            owned[ax] = e.name


def _legacy_plc_udp_to_endpoint(legacy: dict) -> dict:
    axis_ids = legacy.get("axis_ids", ["X"])
    return {
        "name": legacy.get("name", "plc"),
        "bind_host": legacy.get("bind_host", "0.0.0.0"),
        "bind_port": legacy.get("bind_port", legacy.get("rx_port", 50002)),
        "target_host": legacy.get("target_host", "127.0.0.1"),
        "target_port": legacy.get("target_port", legacy.get("tx_port", 50001)),
        "axis_ids": axis_ids,
        "delimiter": legacy.get("delimiter", ";"),
        "encoding": legacy.get("encoding", "ascii"),
        "float_fmt": legacy.get("float_fmt", "{:.6f}"),
        "true_token": legacy.get("true_token", "1"),
        "false_token": legacy.get("false_token", "0"),
    }


def _load_toml(path: Path) -> dict:
    # Python >= 3.11: tomllib (stdlib); else: tomli (dependency)
    try:
        import tomllib  # type: ignore
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except ModuleNotFoundError:
        import tomli  # type: ignore
        return tomli.loads(path.read_text(encoding="utf-8"))
