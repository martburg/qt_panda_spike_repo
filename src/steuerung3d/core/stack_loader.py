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
from typing import Any, Dict, Iterable, List

try:
    import tomllib  # py3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore

from .stack_spec import ServiceSpec, StackSpec


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base.

    Rules:
    - dict + dict => merge keys recursively
    - everything else (including lists) => override replaces base
    """
    out = dict(base)
    for k, v in (override or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _set_by_path(root: dict, dotted: str, value: Any) -> None:
    parts = [p for p in (dotted or "").split(".") if p]
    if not parts:
        raise ValueError("empty --set key")
    cur = root
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _parse_toml_value(s: str) -> Any:
    """Parse a TOML literal value from a CLI string.

    Examples:
      true, 123, 1.2, "text", ['a','b'] (TOML arrays use double quotes)

    If parsing fails, falls back to the raw string.
    """
    if tomllib is None:  # pragma: no cover
        return s
    try:
        # TOML requires double quotes for strings.
        return tomllib.loads(f"v = {s}")["v"]
    except Exception:
        return s


def _apply_sets(data: dict, sets: Iterable[str]) -> dict:
    out = dict(data)
    for item in sets or []:
        if "=" not in item:
            raise ValueError(f"Invalid --set (expected key=value): {item}")
        key, val_s = item.split("=", 1)
        _set_by_path(out, key.strip(), _parse_toml_value(val_s.strip()))
    return out


def _load_toml(path: Path) -> dict:
    if tomllib is None:  # pragma: no cover
        raise RuntimeError("tomllib not available (requires Python 3.11+)")
    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


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
        # Keep consistent semantics: relative paths resolve from cwd (repo root during dev).
        base_dir = Path.cwd()

    # Load base + merge overrides + apply CLI sets.
    data = _load_toml(profile_path)
    for ov in overrides or []:
        ov_path = Path(ov)
        if not ov_path.exists():
            raise FileNotFoundError(ov_path)
        data = _deep_merge(data, _load_toml(ov_path))
    if sets:
        data = _apply_sets(data, sets)

    stack_tbl = data.get("stack", {})
    name = str(stack_tbl.get("name") or profile_path.stem)

    rig_tbl = dict(data.get("rig", {}) or {})
    device_source = str(rig_tbl.get("device_source") or "sim").strip().lower()
    if device_source not in ("sim", "real"):
        raise ValueError(f"Invalid [rig].device_source={device_source!r} (expected 'sim' or 'real')")

    axes = list(rig_tbl.get("axes") or [])
    # In REAL mode the PLCs are already running; axes may be discovered at runtime.
    if not axes and device_source != "real":
        raise ValueError(f"Stack profile {profile_path} has no [rig].axes")

    net_tbl = dict(data.get("net", {}))
    if "bind_host" not in net_tbl:
        net_tbl["bind_host"] = "127.0.0.1"

    services_tbl: Dict[str, Any] = data.get("services", {}) or {}
    services: Dict[str, ServiceSpec] = {}
    for key, tbl in services_tbl.items():
        if not isinstance(tbl, dict):
            continue

        # --- Convenience sugar for "single" profiles ---
        raw_args = list(tbl.get("args", []) or [])
        module_s = str(tbl.get("module", ""))

        # DenSi argument sugar: allow axis/cmd_in/telem_out/dt/wire_proto keys.
        if module_s.endswith(".apps.den_si") or module_s.endswith(".den_si"):
            args2 = list(raw_args)

            def _has_flag(flag: str) -> bool:
                return any(str(a) == flag for a in args2)

            if (not _has_flag("--axis")) and tbl.get("axis"):
                args2 += ["--axis", str(tbl["axis"])]
            if (not _has_flag("--cmd-in")) and tbl.get("cmd_in"):
                args2 += ["--cmd-in", str(tbl["cmd_in"])]
            if (not _has_flag("--telem-out")) and tbl.get("telem_out"):
                args2 += ["--telem-out", str(tbl["telem_out"])]
            if (not _has_flag("--dt")) and tbl.get("dt") is not None:
                args2 += ["--dt", str(tbl["dt"])]

            # NEW: wire protocol selection for DenSi (plc|json). Defaults are enforced in app.
            wire_proto = tbl.get("wire_proto", None)
            if (not _has_flag("--wire-proto")) and wire_proto:
                args2 += ["--wire-proto", str(wire_proto)]

            raw_args = args2

        spec = ServiceSpec(
            enabled=bool(tbl.get("enabled", True)),
            module=module_s,
            mode=str(tbl.get("mode", "single")),
            count=tbl.get("count", None),
            args=raw_args,
            config=tbl.get("config"),
            env=dict(tbl.get("env", {}) or {}),
        )
        services[str(key)] = spec

    if not services:
        raise ValueError(f"Stack profile {profile_path} has no [services.*] entries")

    return StackSpec(
        name=name,
        base_dir=Path(base_dir),
        axes=[str(a) for a in axes],
        rig=rig_tbl,
        net=net_tbl,
        services=services,
    )


def merge_overrides(base: StackSpec, override: StackSpec) -> StackSpec:
    """Shallow merge override values into a base spec.

    This is intentionally conservative: net and services dicts merge by key.
    """
    net = dict(base.net)
    net.update(override.net)

    services = dict(base.services)
    for k, v in override.services.items():
        if k in services:
            # Field-wise override of ServiceSpec
            cur = services[k]
            services[k] = replace(
                cur,
                enabled=v.enabled,
                module=v.module or cur.module,
                mode=v.mode or cur.mode,
                count=v.count if getattr(v, "count", None) is not None else getattr(cur, "count", None),
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
    return StackSpec(name=name, base_dir=base.base_dir, axes=axes, rig=rig, net=net, services=services)
