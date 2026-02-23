from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from steuerung3d.config.toml_loader import load_toml


def _hostport(s: str) -> Tuple[str, int]:
    host, port = s.rsplit(":", 1)
    return host.strip(), int(port)


@dataclass(frozen=True)
class Joy2IntentConfig:
    # --- required ---
    raw_in: Tuple[str, int]
    intent_out: Tuple[str, int]
    tick_hz: float
    stale_after_ms: int

    winches: List[str]
    default_mode: str

    max_winch_mps: float
    fine_scale: float

    axes: Dict[str, int]
    buttons: Dict[str, int]

    deadzone: float
    expo: float
    invert: Dict[str, bool]

    # --- optional / defaults (must come after all non-default fields) ---
    # Buttons that select winches by position (0..N-1). If omitted, defaults to [0,1,2,3].
    select_buttons: List[int] = field(default_factory=lambda: [0, 1, 2, 3])

    # Optional legacy alias (float). If present, overrides max_winch_mps.
    manual_max_v: float | None = None

    # Sync/cartesian limits (currently not used by joy2intent mapping, kept for config completeness).
    sync_max_v: Dict[str, float] = field(default_factory=dict)

    # Identity stamped into motion intents. Must match the claim owner (HiP).
    hip_id: str = "hip"


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

    return Joy2IntentConfig(
        raw_in=_hostport(io.get("raw_in", "127.0.0.1:50100")),
        intent_out=_hostport(io.get("intent_out", "127.0.0.1:51001")),
        tick_hz=float(io.get("tick_hz", 50)),
        stale_after_ms=int(io.get("stale_after_ms", 200)),

        winches=list(rig.get("winches", ["Anton", "Debby", "Cecil", "Burt"])),
        default_mode=str(mode.get("default", "setup_manual")),

        select_buttons=list(rig.get("select_buttons", [0, 1, 2, 3])),

        max_winch_mps=float(lim_m.get("max_winch_mps", 0.30)),
        fine_scale=float(lim_m.get("fine_scale", 0.20)),
        manual_max_v=(float(lim_m["max_v"]) if "max_v" in lim_m and lim_m["max_v"] is not None else None),
        sync_max_v=dict(lim_s.get("max_v", {"x": 0.60, "y": 0.60, "z": 0.40})),

        axes=dict((bindings.get("axes", {}) or {})),
        buttons=dict((bindings.get("buttons", {}) or {})),

        deadzone=float(f.get("deadzone", 0.08)),
        expo=float(f.get("expo", 0.25)),
        invert=dict(f.get("invert", {}) or {}),

        hip_id=str(ident.get("hip_id", "hip")),
    )
