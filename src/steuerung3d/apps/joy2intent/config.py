from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from steuerung3d.config.toml_loader import load_toml


def _hostport(s: str) -> Tuple[str, int]:
    host, port = s.rsplit(":", 1)
    return host.strip(), int(port)


def _require(mapping: dict, key: str, *, ctx: str) -> object:
    if key not in mapping or mapping[key] is None:
        raise ValueError(f"Missing required config key '{ctx}.{key}' in joy2intent config")
    return mapping[key]


@dataclass(frozen=True)
class Joy2IntentConfig:
    # --- required ---
    raw_in: Tuple[str, int]
    intent_out: Tuple[str, int]
    tick_hz: float
    stale_after_ms: int

    winches: List[str]
    # Physical button indices (0..N-1) used to select winches by position.
    select_buttons: List[int]
    default_mode: str

    max_winch_mps: float
    fine_scale: float

    axes: Dict[str, int]
    buttons: Dict[str, int | list[int]]

    deadzone: float
    expo: float
    invert: Dict[str, bool]
    hip_id: str
    sync_max_v: Dict[str, float] = field(default_factory=dict)

    # Identity stamped into motion intents. Must match the claim owner (HiP).


def load_joy2intent_config(path: Path) -> Joy2IntentConfig:
    raw = load_toml(path)

    io = raw.get("io", {}) or {}
    ident = raw.get("identity", {}) or {}
    rig = raw.get("rig", {}) or {}
    mode = raw.get("mode", {}) or {}
    limits = raw.get("limits", {}) or {}
    lim_m = limits.get("manual", {}) or {}
    lim_s = limits.get("sync", {}) or {}
    bindings = raw.get("bindings", {}) or {}
    f = raw.get("filters", {}) or {}

    # Tightened config: avoid silent fallbacks. Fail fast on missing keys.
    # Basic sanity: require at least one winch and at least one select button.
    if not (rig.get("winches") or []):
        raise ValueError("Missing or empty config key 'rig.winches' in joy2intent config")
    if not (rig.get("select_buttons") or []):
        raise ValueError("Missing or empty config key 'rig.select_buttons' in joy2intent config")

    return Joy2IntentConfig(
        raw_in=_hostport(str(_require(io, "raw_in", ctx="io"))),
        intent_out=_hostport(str(_require(io, "intent_out", ctx="io"))),
        tick_hz=float(_require(io, "tick_hz", ctx="io")),
        stale_after_ms=int(_require(io, "stale_after_ms", ctx="io")),
        winches=list(_require(rig, "winches", ctx="rig")),
        default_mode=str(_require(mode, "default", ctx="mode")),
        select_buttons=list(_require(rig, "select_buttons", ctx="rig")),
        max_winch_mps=float(_require(lim_m, "max_winch_mps", ctx="limits.manual")),
        fine_scale=float(_require(lim_m, "fine_scale", ctx="limits.manual")),
        sync_max_v=dict((lim_s.get("max_v") or {})),
        axes=dict(_require(bindings, "axes", ctx="bindings")),
        buttons=dict(_require(bindings, "buttons", ctx="bindings")),
        deadzone=float(_require(f, "deadzone", ctx="filters")),
        expo=float(_require(f, "expo", ctx="filters")),
        invert=dict((f.get("invert") or {})),
        hip_id=str(_require(ident, "hip_id", ctx="identity")),
    )
