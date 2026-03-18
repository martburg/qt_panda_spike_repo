from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from steuerung3d.config.toml_loader import load_toml


def _hostport(s: str) -> tuple[str, int]:
    host, port = s.rsplit(":", 1)
    return host.strip(), int(port)


def _as_table(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): v for k, v in value.items()}


def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except Exception:
            return None
    return None


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    s = str(value)
    return s or None


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


def _int_bool_map(d: dict[str, object] | None) -> dict[int, bool]:
    out: dict[int, bool] = {}
    if not d:
        return out
    for k, v in d.items():
        try:
            out[int(k)] = bool(v)
        except Exception:
            continue
    return out


@dataclass(frozen=True)
class InputdConfig:
    out_addr: tuple[str, int]
    tick_hz: float

    device_index: int | None
    name_contains: str | None
    src: str

    hat_as_buttons: bool
    max_axes: int | None
    max_buttons: int | None

    invert_axes: dict[int, bool]

    deadzone: float
    expo: float
    smoothing_alpha: float


def load_inputd_config(path: Path) -> InputdConfig:
    raw = _as_table(load_toml(path))

    io = _as_table(raw.get("io", {}))
    dev = _as_table(raw.get("device", {}))
    opt = _as_table(raw.get("options", {}))
    norm = _as_table(raw.get("normalize", {}))
    filt = _as_table(raw.get("filter", {}))

    return InputdConfig(
        out_addr=_hostport(str(io.get("out", "127.0.0.1:50100"))),
        tick_hz=_as_float(io.get("tick_hz", 60.0), 60.0),
        device_index=_as_optional_int(dev.get("index", None)),
        name_contains=_as_optional_str(dev.get("name_contains", None)),
        src=str(dev.get("src", "gamepad")),
        hat_as_buttons=bool(opt.get("hat_as_buttons", True)),
        max_axes=_as_optional_int(opt.get("max_axes", None)),
        max_buttons=_as_optional_int(opt.get("max_buttons", None)),
        invert_axes=_int_bool_map(_as_table(norm.get("invert_axes", {}))),
        deadzone=_as_float(filt.get("deadzone", 0.0), 0.0),
        expo=_as_float(filt.get("expo", 0.0), 0.0),
        smoothing_alpha=_as_float(filt.get("smoothing_alpha", 0.0), 0.0),
    )
