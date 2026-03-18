from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from steuerung3d.config.toml_loader import load_toml


def _hostport(s: str) -> Tuple[str, int]:
    host, port = s.rsplit(":", 1)
    return host.strip(), int(port)


def _as_table(value: object) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_optional_int(value: object) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def _as_optional_str(value: object) -> Optional[str]:
    if value is None:
        return None
    s = str(value)
    return s or None


def _int_bool_map(d: Dict[str, Any] | None) -> Dict[int, bool]:
    out: Dict[int, bool] = {}
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
    out_addr: Tuple[str, int]
    tick_hz: float

    device_index: Optional[int]
    name_contains: Optional[str]
    src: str

    hat_as_buttons: bool
    max_axes: Optional[int]
    max_buttons: Optional[int]

    invert_axes: Dict[int, bool]

    deadzone: float
    expo: float
    smoothing_alpha: float


def load_inputd_config(path: Path) -> InputdConfig:
    raw = load_toml(path)

    io = _as_table(raw.get("io", {}))
    dev = _as_table(raw.get("device", {}))
    opt = _as_table(raw.get("options", {}))
    norm = _as_table(raw.get("normalize", {}))
    filt = _as_table(raw.get("filter", {}))

    return InputdConfig(
        out_addr=_hostport(io.get("out", "127.0.0.1:50100")),
        tick_hz=float(io.get("tick_hz", 60)),
        device_index=_as_optional_int(dev.get("index", None)),
        name_contains=_as_optional_str(dev.get("name_contains", None)),
        src=str(dev.get("src", "gamepad")),
        hat_as_buttons=bool(opt.get("hat_as_buttons", True)),
        max_axes=_as_optional_int(opt.get("max_axes", None)),
        max_buttons=_as_optional_int(opt.get("max_buttons", None)),
        invert_axes=_int_bool_map(norm.get("invert_axes", {}) or {}),
        deadzone=float(filt.get("deadzone", 0.0)),
        expo=float(filt.get("expo", 0.0)),
        smoothing_alpha=float(filt.get("smoothing_alpha", 0.0)),
    )
