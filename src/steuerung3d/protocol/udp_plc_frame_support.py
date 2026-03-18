"""Frame/field helpers for legacy UDP PLC channels.

Split out of :mod:`steuerung3d.protocol.udp_plc_channels` as a Lane-1 refactor
with no intended semantic changes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, cast

from steuerung3d.protocol.udp_plc_coerce import to_float

PARAM_GROUP_DEFAULTS: Dict[str, List[str]] = {
    "pos": ["HardMax", "UserMax", "UserMin", "HardMin", "PosWin"],
    "vel": ["VelMax", "VelWin", "AccMax", "AccMove", "DccMax", "MaxAmp", "VelMaxMot"],
    "filter": ["P", "I", "D", "IL", "RampForm"],
    "guider": ["PosMax", "PosMin", "Pitch"],
}


def axis_id_or_default(axis_id: Optional[str], default: str = "X") -> str:
    value = str(axis_id or default).strip()
    return value or default


def frame_axis_id(frame: Any, default: str = "X") -> str:
    try:
        axes = getattr(frame, "axes", {}) or {}
    except Exception:
        return default
    if isinstance(axes, Mapping) and axes:
        try:
            axis_keys = cast(Mapping[object, object], axes).keys()
            return axis_id_or_default(str(next(iter(axis_keys))), default)
        except Exception:
            return default
    return default


def frame_lifetick_ui_rx(frame: Any, axis_id: str) -> int:
    try:
        echo = getattr(frame, "lifetick_echo", {}) or {}
    except Exception:
        return 0
    if isinstance(echo, Mapping) and axis_id in echo:
        try:
            echo_map = cast(Mapping[object, object], echo)
            value = echo_map[axis_id]
            if isinstance(value, (bool, int)):
                return int(value)
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                return int(float(value))
            return 0
        except Exception:
            return 0
    return 0


def extract_param_write_values(
    fields: Mapping[str, object],
    *,
    group_defaults: Mapping[str, List[str]],
    param_keymap: Mapping[str, str],
) -> List[tuple[str, Dict[str, float]]]:
    out: List[tuple[str, Dict[str, float]]] = []
    for grp, keys in group_defaults.items():
        values: Dict[str, float] = {}
        for key in keys:
            plc_key = param_keymap.get(key)
            if not plc_key or plc_key not in fields:
                continue
            values[str(key)] = to_float(fields.get(plc_key, "0"), 0.0)
        if values:
            out.append((str(grp), values))
    return out


def frame_param_map(frame: Any) -> Dict[str, float]:
    params: Dict[str, float] = {}
    try:
        from steuerung3d.core.command_frame import ParamWriteOp, coerce_param_ops

        for op in coerce_param_ops(getattr(frame, "param_ops", []) or []):
            if not isinstance(op, ParamWriteOp):
                continue
            for key, value in dict(op.values or {}).items():
                try:
                    params[str(key)] = float(value)
                except Exception:
                    continue
    except Exception:
        return {}
    return params
