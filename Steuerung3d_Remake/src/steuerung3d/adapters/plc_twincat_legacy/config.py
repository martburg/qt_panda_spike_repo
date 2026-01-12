from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import tomllib

from steuerung3d.adapters.plc_twincat_legacy.device import TwinCATLegacyWinchUdpDevice
from steuerung3d.adapters.plc_twincat_legacy.fleet import TwinCATLegacyWinchFleetDevice


def _get(d: Mapping[str, Any], key: str, default: Any = None) -> Any:
    return d[key] if key in d else default


def _require(d: Mapping[str, Any], key: str) -> Any:
    if key not in d:
        raise KeyError(f"Missing required config key: {key}")
    return d[key]


@dataclass(frozen=True)
class PlcTwincatLegacyFleetConfig:
    controller_ip: str
    remote_port: int = 15001
    timeout_s: float = 0.02
    modus: str = "E"
    intent: bool = True


def load_plc_twincat_legacy_fleet_from_toml(path: str | Path) -> TwinCATLegacyWinchFleetDevice:
    cfg = tomllib.loads(Path(path).read_text(encoding="utf-8"))

    device = _require(cfg, "device")
    kind = _require(device, "kind")
    if kind != "plc_twincat_legacy_fleet":
        raise ValueError(f"Unsupported device.kind={kind!r} (expected 'plc_twincat_legacy_fleet')")

    root = _require(device, "plc_twincat_legacy_fleet")
    defaults_raw: Dict[str, Any] = dict(_get(root, "defaults", {}))

    defaults = PlcTwincatLegacyFleetConfig(
        controller_ip=_require(defaults_raw, "controller_ip"),
        remote_port=int(_get(defaults_raw, "remote_port", 15001)),
        timeout_s=float(_get(defaults_raw, "timeout_s", 0.02)),
        modus=str(_get(defaults_raw, "modus", "E")),
        intent=bool(_get(defaults_raw, "intent", True)),
    )

    axes = _require(root, "axes")
    if not isinstance(axes, list) or not axes:
        raise ValueError("device.plc_twincat_legacy_fleet.axes must be a non-empty list")

    devices: List[TwinCATLegacyWinchUdpDevice] = []
    for a in axes:
        axis_id = str(_require(a, "axis_id"))
        remote_ip = str(_require(a, "remote_ip"))
        local_port = int(_require(a, "local_port"))

        # Optional overrides per axis
        remote_port = int(_get(a, "remote_port", defaults.remote_port))
        controller_ip = str(_get(a, "controller_ip", defaults.controller_ip))
        timeout_s = float(_get(a, "timeout_s", defaults.timeout_s))
        modus = str(_get(a, "modus", defaults.modus))
        intent = bool(_get(a, "intent", defaults.intent))

        devices.append(
            TwinCATLegacyWinchUdpDevice(
                axis_id=axis_id,
                remote=(remote_ip, remote_port),
                local=(controller_ip, local_port),
                timeout_s=timeout_s,
                modus=modus,
                intent=intent,
            )
        )

    return TwinCATLegacyWinchFleetDevice(devices=devices)
