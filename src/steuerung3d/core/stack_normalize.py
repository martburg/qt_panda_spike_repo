from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .stack_spec import FanoutMode, ServiceSpec, StackSpec


def _as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): v for k, v in value.items()}


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _as_env_dict(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): str(v) for k, v in value.items()}


def _as_fanout_mode(value: object) -> FanoutMode:
    mode = str(value or "single").strip().lower()
    return "per_axis" if mode == "per_axis" else "single"


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _normalize_den_si_args(
    *, module_s: str, raw_args: list[object], tbl: Mapping[str, object]
) -> list[object]:
    if not (module_s.endswith(".apps.den_si") or module_s.endswith(".den_si")):
        return list(raw_args)

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
    if (not _has_flag("--wire-proto")) and tbl.get("wire_proto"):
        args2 += ["--wire-proto", str(tbl["wire_proto"])]
    return args2


def services_from_table(services_tbl: Mapping[str, object]) -> dict[str, ServiceSpec]:
    services: dict[str, ServiceSpec] = {}
    for key, raw_tbl in services_tbl.items():
        tbl = _as_dict(raw_tbl)
        if not tbl:
            continue

        module_s = str(tbl.get("module", ""))
        raw_args = _normalize_den_si_args(
            module_s=module_s,
            raw_args=_as_list(tbl.get("args")),
            tbl=tbl,
        )
        spec = ServiceSpec(
            enabled=bool(tbl.get("enabled", True)),
            module=module_s,
            mode=_as_fanout_mode(tbl.get("mode", "single")),
            count=tbl.get("count", None),
            args=raw_args,
            config=_as_optional_str(tbl.get("config")),
            env=_as_env_dict(tbl.get("env")),
        )
        services[str(key)] = spec
    return services


def stack_spec_from_data(
    *, data: dict[str, object], profile_path: Path, base_dir: Path
) -> StackSpec:
    stack_tbl = _as_dict(data.get("stack"))
    name = str(stack_tbl.get("name") or profile_path.stem)

    rig_tbl = _as_dict(data.get("rig"))
    device_source = str(rig_tbl.get("device_source") or "sim").strip().lower()
    if device_source not in ("sim", "real"):
        raise ValueError(
            f"Invalid [rig].device_source={device_source!r} (expected 'sim' or 'real')"
        )

    axes = _as_list(rig_tbl.get("axes"))
    if not axes and device_source != "real":
        raise ValueError(f"Stack profile {profile_path} has no [rig].axes")

    net_tbl = _as_dict(data.get("net"))
    if "bind_host" not in net_tbl:
        net_tbl["bind_host"] = "127.0.0.1"

    services_tbl = _as_dict(data.get("services"))
    services = services_from_table(services_tbl)
    if not services:
        raise ValueError(f"Stack profile {profile_path} has no [services.*] entries")

    return StackSpec(
        name=name,
        base_dir=base_dir,
        profile_path=profile_path,
        axes=[str(a) for a in axes],
        rig=rig_tbl,
        net=net_tbl,
        services=services,
    )
