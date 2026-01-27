from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from steuerung3d.config.toml_loader import load_toml


def _hostport(s: str) -> Tuple[str, int]:
    host, port = s.rsplit(":", 1)
    return host.strip(), int(port)


@dataclass(frozen=True)
class Joy2IntentConfig:
    raw_in: Tuple[str, int]
    intent_out: Tuple[str, int]
    tick_hz: float
    stale_after_ms: int

    winches: List[str]
    default_mode: str

    max_winch_mps: float
    fine_scale: float
    max_v: Dict[str, float]

    axes: Dict[str, int]
    buttons: Dict[str, int]

    deadzone: float
    expo: float
    invert: Dict[str, bool]


def load_joy2intent_config(path: Path) -> Joy2IntentConfig:
    raw = load_toml(path)

    io = raw.get("io", {}) or {}
    rig = raw.get("rig", {}) or {}
    mode = raw.get("mode", {}) or {}
    limits = raw.get("limits", {}) or {}
    lim_m = limits.get("manual", {}) or {}
    lim_s = limits.get("sync", {}) or {}
    bindings = raw.get("bindings", {}) or {}
    f = raw.get("filters", {}) or {}

    return Joy2IntentConfig(
        raw_in=_hostport(io.get("raw_in", "127.0.0.1:50100")),
        intent_out=_hostport(io.get("intent_out", "127.0.0.1:51001")),
        tick_hz=float(io.get("tick_hz", 50)),
        stale_after_ms=int(io.get("stale_after_ms", 200)),

        winches=list(rig.get("winches", ["Anton", "Debby", "Cecil", "Burt"])),
        default_mode=str(mode.get("default", "setup_manual")),

        max_winch_mps=float(lim_m.get("max_winch_mps", 0.30)),
        fine_scale=float(lim_m.get("fine_scale", 0.20)),
        max_v=dict(lim_s.get("max_v", {"x": 0.60, "y": 0.60, "z": 0.40})),

        axes=dict((bindings.get("axes", {}) or {})),
        buttons=dict((bindings.get("buttons", {}) or {})),

        deadzone=float(f.get("deadzone", 0.08)),
        expo=float(f.get("expo", 0.25)),
        invert=dict(f.get("invert", {}) or {}),
    )
