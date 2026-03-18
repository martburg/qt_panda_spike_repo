from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from steuerung3d.config.toml_loader import load_toml


def _hostport(s: str) -> tuple[str, int]:
    host, port = s.rsplit(":", 1)
    return host.strip(), int(port)


def _as_table(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(k): v for k, v in mapping.items()}


def _as_object_list(value: object) -> list[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(cast(Sequence[object], value))


def _require_value(mapping: Mapping[str, object], key: str, *, ctx: str) -> object:
    if key not in mapping or mapping[key] is None:
        raise ValueError(f"Missing required config key '{ctx}.{key}' in joy2intent config")
    return mapping[key]


def _require_section(mapping: Mapping[str, object], key: str, *, ctx: str) -> dict[str, object]:
    value = _require_value(mapping, key, ctx=ctx)
    table = _as_table(value)
    if not table and not isinstance(value, Mapping):
        raise ValueError(f"Config key '{ctx}.{key}' must be a table in joy2intent config")
    return table


def _require_str(mapping: Mapping[str, object], key: str, *, ctx: str) -> str:
    value = _require_value(mapping, key, ctx=ctx)
    if not isinstance(value, str):
        raise ValueError(f"Config key '{ctx}.{key}' must be a string in joy2intent config")
    return value


def _require_float(mapping: Mapping[str, object], key: str, *, ctx: str) -> float:
    value = _require_value(mapping, key, ctx=ctx)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Config key '{ctx}.{key}' must be numeric in joy2intent config")
    return float(value)


def _require_int(mapping: Mapping[str, object], key: str, *, ctx: str) -> int:
    value = _require_value(mapping, key, ctx=ctx)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Config key '{ctx}.{key}' must be an integer in joy2intent config")
    return int(value)


def _require_list_str(mapping: Mapping[str, object], key: str, *, ctx: str) -> list[str]:
    value = _require_value(mapping, key, ctx=ctx)
    items = _as_object_list(value)
    if not items:
        raise ValueError(f"Config key '{ctx}.{key}' must be a list of strings in joy2intent config")
    result: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise ValueError(
                f"Config key '{ctx}.{key}' must be a list of strings in joy2intent config"
            )
        result.append(item)
    return result


def _require_list_int(mapping: Mapping[str, object], key: str, *, ctx: str) -> list[int]:
    value = _require_value(mapping, key, ctx=ctx)
    items = _as_object_list(value)
    if not items:
        raise ValueError(
            f"Config key '{ctx}.{key}' must be a list of integers in joy2intent config"
        )
    result: list[int] = []
    for item in items:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(
                f"Config key '{ctx}.{key}' must be a list of integers in joy2intent config"
            )
        result.append(int(item))
    return result


def _require_dict_str_int_or_int_list(
    mapping: Mapping[str, object], key: str, *, ctx: str
) -> dict[str, int | list[int]]:
    value = _require_value(mapping, key, ctx=ctx)
    table = _as_table(value)
    if not table and not isinstance(value, Mapping):
        raise ValueError(
            f"Config key '{ctx}.{key}' must be a table of button bindings in joy2intent config"
        )
    result: dict[str, int | list[int]] = {}
    for name, raw_value in table.items():
        if isinstance(raw_value, int) and not isinstance(raw_value, bool):
            result[name] = int(raw_value)
            continue
        items = _as_object_list(raw_value)
        if items:
            ints: list[int] = []
            for item in items:
                if not isinstance(item, int) or isinstance(item, bool):
                    raise ValueError(
                        f"Config key '{ctx}.{key}.{name}' must be an int or list[int] in joy2intent config"
                    )
                ints.append(int(item))
            result[name] = ints
            continue
        raise ValueError(
            f"Config key '{ctx}.{key}.{name}' must be an int or list[int] in joy2intent config"
        )
    return result


def _require_dict_str_int(mapping: Mapping[str, object], key: str, *, ctx: str) -> dict[str, int]:
    value = _require_value(mapping, key, ctx=ctx)
    table = _as_table(value)
    if not table and not isinstance(value, Mapping):
        raise ValueError(f"Config key '{ctx}.{key}' must be a table in joy2intent config")
    result: dict[str, int] = {}
    for name, raw_value in table.items():
        if not isinstance(raw_value, int) or isinstance(raw_value, bool):
            raise ValueError(
                f"Config key '{ctx}.{key}' must be a table[str, int] in joy2intent config"
            )
        result[name] = int(raw_value)
    return result


def _optional_bool(mapping: Mapping[str, object], key: str, default: bool) -> bool:
    raw_value = mapping.get(key)
    if raw_value is None:
        return default
    if not isinstance(raw_value, bool):
        raise ValueError(f"Config key '{key}' must be a boolean in joy2intent config")
    return raw_value


def _require_dict_str_bool(mapping: Mapping[str, object], key: str, *, ctx: str) -> dict[str, bool]:
    value = _require_value(mapping, key, ctx=ctx)
    table = _as_table(value)
    if not table and not isinstance(value, Mapping):
        raise ValueError(f"Config key '{ctx}.{key}' must be a table in joy2intent config")
    result: dict[str, bool] = {}
    for name, raw_value in table.items():
        if not isinstance(raw_value, bool):
            raise ValueError(
                f"Config key '{ctx}.{key}' must be a table[str, bool] in joy2intent config"
            )
        result[name] = raw_value
    return result


def _optional_dict_str_float(mapping: Mapping[str, object], key: str) -> dict[str, float]:
    raw_value = mapping.get(key)
    if raw_value is None:
        return {}
    table = _as_table(raw_value)
    if not table and not isinstance(raw_value, Mapping):
        raise ValueError(f"Config key '{key}' must be a table[str, float] in joy2intent config")
    result: dict[str, float] = {}
    for name, item in table.items():
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise ValueError(f"Config key '{key}' must be a table[str, float] in joy2intent config")
        result[name] = float(item)
    return result


@dataclass(frozen=True)
class Joy2IntentConfig:
    raw_in: tuple[str, int]
    intent_out: tuple[str, int]
    context_in: tuple[str, int]
    tick_hz: float
    stale_after_ms: int
    winches: list[str]
    select_buttons: list[int]
    default_mode: str
    max_winch_mps: float
    fine_scale: float
    axes: dict[str, int]
    buttons: dict[str, int | list[int]]
    deadzone: float
    expo: float
    invert: dict[str, bool]
    hip_id: str
    publish_local_manual: bool = True
    sync_max_v: dict[str, float] = field(default_factory=dict)


def load_joy2intent_config(path: Path) -> Joy2IntentConfig:
    raw = load_toml(path)

    io = _require_section(raw, "io", ctx="<root>")
    ident = _require_section(raw, "identity", ctx="<root>")
    rig = _require_section(raw, "rig", ctx="<root>")
    mode = _require_section(raw, "mode", ctx="<root>")
    limits = _require_section(raw, "limits", ctx="<root>")
    lim_m = _require_section(limits, "manual", ctx="limits")
    bindings = _require_section(raw, "bindings", ctx="<root>")
    filters = _require_section(raw, "filters", ctx="<root>")

    winches = _require_list_str(rig, "winches", ctx="rig")
    if not winches:
        raise ValueError("Missing or empty config key 'rig.winches' in joy2intent config")

    select_buttons = _require_list_int(rig, "select_buttons", ctx="rig")
    if not select_buttons:
        raise ValueError("Missing or empty config key 'rig.select_buttons' in joy2intent config")

    lim_s = limits.get("sync")
    lim_s_table = _as_table(lim_s)
    if lim_s is not None and not lim_s_table and not isinstance(lim_s, Mapping):
        raise ValueError("Config key 'limits.sync' must be a table in joy2intent config")
    sync_max_v: dict[str, float] = (
        _optional_dict_str_float(lim_s_table, "max_v") if lim_s_table else {}
    )

    return Joy2IntentConfig(
        raw_in=_hostport(_require_str(io, "raw_in", ctx="io")),
        intent_out=_hostport(_require_str(io, "intent_out", ctx="io")),
        context_in=_hostport(_require_str(io, "context_in", ctx="io")),
        tick_hz=_require_float(io, "tick_hz", ctx="io"),
        stale_after_ms=_require_int(io, "stale_after_ms", ctx="io"),
        winches=winches,
        default_mode=_require_str(mode, "default", ctx="mode"),
        select_buttons=select_buttons,
        max_winch_mps=_require_float(lim_m, "max_winch_mps", ctx="limits.manual"),
        fine_scale=_require_float(lim_m, "fine_scale", ctx="limits.manual"),
        publish_local_manual=_optional_bool(mode, "publish_local_manual", True),
        sync_max_v=sync_max_v,
        axes=_require_dict_str_int(bindings, "axes", ctx="bindings"),
        buttons=_require_dict_str_int_or_int_list(bindings, "buttons", ctx="bindings"),
        deadzone=_require_float(filters, "deadzone", ctx="filters"),
        expo=_require_float(filters, "expo", ctx="filters"),
        invert=_require_dict_str_bool(filters, "invert", ctx="filters"),
        hip_id=_require_str(ident, "hip_id", ctx="identity"),
    )
