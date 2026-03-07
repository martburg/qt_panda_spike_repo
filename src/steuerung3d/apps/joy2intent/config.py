from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from steuerung3d.config.toml_loader import load_toml


def _hostport(s: str) -> Tuple[str, int]:
    host, port = s.rsplit(":", 1)
    return host.strip(), int(port)


def _require(mapping: dict, key: str, *, ctx: str) -> object:
    if key not in mapping or mapping[key] is None:
        raise ValueError(f"Missing required config key '{ctx}.{key}' in joy2intent config")
    return mapping[key]

def _int_list(value: Any, *, ctx: str) -> List[int]:
    if isinstance(value, bool):
        raise ValueError(f"Invalid boolean for {ctx}; expected int or list[int]")
    if isinstance(value, int):
        return [int(value)]
    if isinstance(value, list):
        out: List[int] = []
        for idx, item in enumerate(value):
            if isinstance(item, bool):
                raise ValueError(f"Invalid boolean for {ctx}[{idx}]; expected int")
            try:
                out.append(int(item))
            except Exception as e:
                raise ValueError(f"Invalid button index for {ctx}[{idx}]: {item!r}") from e
        return out
    raise ValueError(f"Invalid value for {ctx}; expected int or list[int], got {type(value).__name__}")


def _button_map(mapping: dict, *, ctx: str) -> Dict[str, List[int]]:
    out: Dict[str, List[int]] = {}
    for key, value in mapping.items():
        out[str(key)] = _int_list(value, ctx=f"{ctx}.{key}")
    return out


def _select_groups(value: Any, *, ctx: str) -> List[List[int]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Missing or empty config key '{ctx}' in joy2intent config")
    out: List[List[int]] = []
    for idx, item in enumerate(value):
        out.append(_int_list(item, ctx=f"{ctx}[{idx}]") )
    return out



@dataclass(frozen=True)
class Joy2IntentConfig:
    # --- required ---
    raw_in: Tuple[str, int]
    intent_out: Tuple[str, int]
    tick_hz: float
    stale_after_ms: int

    winches: List[str]
    # Physical button indices/groups used to select winches by position.
    # Each winch slot may be driven by one button or several alias buttons.
    select_buttons: List[List[int]]
    default_mode: str

    max_winch_mps: float
    fine_scale: float

    axes: Dict[str, int]
    buttons: Dict[str, int]

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
        select_buttons=_select_groups(_require(rig, "select_buttons", ctx="rig"), ctx="rig.select_buttons"),
        max_winch_mps=float(_require(lim_m, "max_winch_mps", ctx="limits.manual")),
        fine_scale=float(_require(lim_m, "fine_scale", ctx="limits.manual")),
        sync_max_v=dict((lim_s.get("max_v") or {})),
        axes=dict(_require(bindings, "axes", ctx="bindings")),
        buttons=_button_map(dict(_require(bindings, "buttons", ctx="bindings")), ctx="bindings.buttons"),
        deadzone=float(_require(f, "deadzone", ctx="filters")),
        expo=float(_require(f, "expo", ctx="filters")),
        invert=dict((f.get("invert") or {})),
        hip_id=str(_require(ident, "hip_id", ctx="identity")),
    )
