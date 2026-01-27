from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from steuerung3d.config.toml_loader import load_toml


def _hostport(s: str) -> Tuple[str, int]:
    host, port = s.rsplit(":", 1)
    return host.strip(), int(port)


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

    io = raw.get("io", {}) or {}
    dev = raw.get("device", {}) or {}
    opt = raw.get("options", {}) or {}
    norm = raw.get("normalize", {}) or {}
    filt = raw.get("filter", {}) or {}

    return InputdConfig(
        out_addr=_hostport(io.get("out", "127.0.0.1:50100")),
        tick_hz=float(io.get("tick_hz", 60)),
        device_index=dev.get("index", None),
        name_contains=dev.get("name_contains", None),
        src=str(dev.get("src", "gamepad")),
        hat_as_buttons=bool(opt.get("hat_as_buttons", True)),
        max_axes=opt.get("max_axes", None),
        max_buttons=opt.get("max_buttons", None),
        invert_axes=_int_bool_map(norm.get("invert_axes", {}) or {}),
        deadzone=float(filt.get("deadzone", 0.0)),
        expo=float(filt.get("expo", 0.0)),
        smoothing_alpha=float(filt.get("smoothing_alpha", 0.0)),
    )
