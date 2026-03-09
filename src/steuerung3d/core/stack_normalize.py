from __future__ import annotations

from typing import Any, Dict

from .stack_spec import ServiceSpec, StackSpec


def _normalize_den_si_args(
    *, module_s: str, raw_args: list[object], tbl: dict[str, Any]
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


def services_from_table(services_tbl: Dict[str, Any]) -> Dict[str, ServiceSpec]:
    services: Dict[str, ServiceSpec] = {}
    for key, tbl in services_tbl.items():
        if not isinstance(tbl, dict):
            continue

        raw_args = _normalize_den_si_args(
            module_s=str(tbl.get("module", "")),
            raw_args=list(tbl.get("args", []) or []),
            tbl=tbl,
        )
        spec = ServiceSpec(
            enabled=bool(tbl.get("enabled", True)),
            module=str(tbl.get("module", "")),
            mode=str(tbl.get("mode", "single")),
            count=tbl.get("count", None),
            args=raw_args,
            config=tbl.get("config"),
            env=dict(tbl.get("env", {}) or {}),
        )
        services[str(key)] = spec
    return services


def stack_spec_from_data(*, data: dict, profile_path, base_dir) -> StackSpec:
    stack_tbl = data.get("stack", {})
    name = str(stack_tbl.get("name") or profile_path.stem)

    rig_tbl = dict(data.get("rig", {}) or {})
    device_source = str(rig_tbl.get("device_source") or "sim").strip().lower()
    if device_source not in ("sim", "real"):
        raise ValueError(
            f"Invalid [rig].device_source={device_source!r} (expected 'sim' or 'real')"
        )

    axes = list(rig_tbl.get("axes") or [])
    if not axes and device_source != "real":
        raise ValueError(f"Stack profile {profile_path} has no [rig].axes")

    net_tbl = dict(data.get("net", {}))
    if "bind_host" not in net_tbl:
        net_tbl["bind_host"] = "127.0.0.1"

    services_tbl: Dict[str, Any] = data.get("services", {}) or {}
    services = services_from_table(services_tbl)
    if not services:
        raise ValueError(f"Stack profile {profile_path} has no [services.*] entries")

    return StackSpec(
        name=name,
        base_dir=base_dir,
        axes=[str(a) for a in axes],
        rig=rig_tbl,
        net=net_tbl,
        services=services,
    )
