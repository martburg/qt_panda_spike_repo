from __future__ import annotations

from pathlib import Path

from steuerung3d.config.toml_loader import load_toml

from .models import PairConfig, SupervisorProfile


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _as_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def load_profile(path: str | Path) -> SupervisorProfile:
    raw = dict(load_toml(Path(path)))
    sup = dict(raw.get("supervisor", {}) or {})
    pair_items = list(raw.get("pairs", []) or [])
    pairs: list[PairConfig] = []
    seen_pair_ids: set[str] = set()
    seen_axis_ids: set[str] = set()
    for item in pair_items:
        d = dict(item or {})
        pair_id = _as_str(d.get("pair_id")).strip()
        axis_id = _as_str(d.get("axis_id", pair_id)).strip()
        densi_id = _as_str(d.get("densi_id", axis_id)).strip()
        hip_id = _as_str(d.get("hip_id", f"hip_{pair_id}")).strip()
        if not pair_id or not axis_id:
            raise ValueError(f"invalid pair entry: {d!r}")
        if pair_id in seen_pair_ids:
            raise ValueError(f"duplicate supervisor pair_id: {pair_id}")
        if axis_id in seen_axis_ids:
            raise ValueError(f"duplicate supervisor axis_id: {axis_id}")
        seen_pair_ids.add(pair_id)
        seen_axis_ids.add(axis_id)
        pairs.append(
            PairConfig(
                pair_id=pair_id,
                axis_id=axis_id,
                densi_id=densi_id,
                hip_id=hip_id,
                selected=_as_bool(d.get("selected"), True),
                densi_action_out=_as_str(d.get("densi_action_out", "")).strip(),
                hip_launch=_as_str(d.get("hip_launch", "")).strip(),
                densi_launch=_as_str(d.get("densi_launch", "")).strip(),
            )
        )
    launch = dict(raw.get("launch", {}) or {})
    profile = SupervisorProfile(
        supervisor_id=_as_str(sup.get("id", "supervisor")).strip() or "supervisor",
        title=_as_str(sup.get("title", sup.get("id", "Supervisor"))).strip() or "Supervisor",
        cycle_ms=max(20, _as_int(sup.get("cycle_ms", 50), 50)),
        telem_in=_as_str(sup.get("telem_in", "127.0.0.1:51002")).strip(),
        intent_out=_as_str(sup.get("intent_out", "127.0.0.1:51001")).strip(),
        gui=_as_bool(sup.get("gui"), True),
        stale_after_ms=max(200, _as_int(sup.get("stale_after_ms", 800), 800)),
        launch_stack=_as_str(launch.get("stack_profile", "")).strip(),
        pairs=tuple(pairs),
    )
    if not profile.pairs:
        raise ValueError("supervisor profile must define at least one pair")
    return profile
