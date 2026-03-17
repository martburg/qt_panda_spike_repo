"""Load stack profiles (TOML) into :class:`~steuerung3d.core.stack_spec.StackSpec`.

The profile format is intentionally straightforward. Example:

    [stack]
    name = "dev_sim"
    keep_last_sessions = 5

    [rig]
    axes = ["Anton","Debby"]

    [net]
    bind_host = "127.0.0.1"
    cmd_base = 52001
    ui_telem_base = 51002
    dev_telem_in = "127.0.0.1:52020"

    [services.core]
    enabled = true
    module = "steuerung3d.apps.core_udp_service"
    mode = "single"
    args = ["--dev-telem-in", "{net.dev_telem_in}", ...]

    [services.densi]
    enabled = true
    module = "steuerung3d.apps.den_si"
    mode = "per_axis"
    args = ["--axis", "{axis}", "--cmd-in", "{net.bind_host}:{net.cmd_base+axis_index}", ...]

Notes:
- args entries are rendered as expressions in braces with a safe evaluator.
- If a rendered arg yields a list, it is spliced into argv.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import List

from .stack_merge import apply_sets, deep_merge
from .stack_normalize import stack_spec_from_data
from .stack_spec import StackSpec
from .stack_toml import load_toml, parse_toml_value


def load_stack_profile(
    profile_path: Path,
    *,
    base_dir: Path | None = None,
    overrides: List[Path] | None = None,
    sets: List[str] | None = None,
) -> StackSpec:
    """Load a TOML profile from disk, applying optional overrides.

    Args:
        profile_path: Base profile (TOML)
        base_dir: Working directory for subprocesses (defaults to cwd)
        overrides: Optional list of TOML override files, applied in order
        sets: Optional list of CLI overrides in the form "a.b.c=value". Applied last.
    """
    profile_path = Path(profile_path)
    if not profile_path.exists():
        raise FileNotFoundError(profile_path)

    if base_dir is None:
        base_dir = Path.cwd()

    data = load_toml(profile_path)
    for ov in overrides or []:
        ov_path = Path(ov)
        if not ov_path.exists():
            raise FileNotFoundError(ov_path)
        data = deep_merge(data, load_toml(ov_path))
    if sets:
        data = apply_sets(data, sets, parse_value=parse_toml_value)

    return stack_spec_from_data(data=data, profile_path=profile_path, base_dir=Path(base_dir))


def merge_overrides(base: StackSpec, override: StackSpec) -> StackSpec:
    """Shallow merge override values into a base spec.

    This is intentionally conservative: net and services dicts merge by key.
    """
    net = dict(base.net)
    net.update(override.net)

    services = dict(base.services)
    for k, v in override.services.items():
        if k in services:
            cur = services[k]
            services[k] = replace(
                cur,
                enabled=v.enabled,
                module=v.module or cur.module,
                mode=v.mode or cur.mode,
                count=v.count
                if getattr(v, "count", None) is not None
                else getattr(cur, "count", None),
                args=v.args or cur.args,
                config=v.config if v.config is not None else cur.config,
                env={**cur.env, **(v.env or {})},
            )
        else:
            services[k] = v

    axes = override.axes or base.axes
    name = override.name or base.name
    rig = dict(getattr(base, "rig", {}) or {})
    rig.update(getattr(override, "rig", {}) or {})
    return StackSpec(
        name=name,
        base_dir=base.base_dir,
        profile_path=override.profile_path or base.profile_path,
        axes=axes,
        rig=rig,
        net=net,
        services=services,
    )
