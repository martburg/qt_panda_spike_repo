from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Mapping, Union

from .param_groups import ParamGroup, coerce_param_group

JsonMap = Mapping[object, object]


def _as_object_dict(value: object) -> dict[object, object]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _new_str_float_dict() -> Dict[str, float]:
    return {}


def _new_param_ops_list() -> List[ParamOp]:
    return []


def _new_str_int_dict() -> Dict[str, int]:
    return {}


def _new_str_bool_dict() -> Dict[str, bool]:
    return {}


@dataclass(frozen=True)
class AxisSetpoint:
    enable: bool
    vel: float  # units/s (placeholder)


@dataclass(frozen=True)
class ParamEditBeginOp:
    type: Literal["param_edit_begin"] = "param_edit_begin"
    group: ParamGroup = "pos"


@dataclass(frozen=True)
class ParamWriteOp:
    type: Literal["param_write"] = "param_write"
    group: ParamGroup = "pos"
    values: Dict[str, float] = field(default_factory=_new_str_float_dict)


@dataclass(frozen=True)
class ParamCancelOp:
    type: Literal["param_cancel"] = "param_cancel"
    group: ParamGroup = "pos"


ParamOp = Union[ParamEditBeginOp, ParamWriteOp, ParamCancelOp]


def decode_param_ops(payload: Any) -> List[ParamOp]:
    """Decode param operations from a JSON-like structure.

    We keep this tolerant: unknown ops are ignored.
    """
    if payload is None or not isinstance(payload, list):
        return []

    out: List[ParamOp] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        item_dict: JsonMap = item
        op_type = str(item_dict.get("type", "") or "")
        group = coerce_param_group(str(item_dict.get("group", "pos") or "pos"))
        if op_type == "param_edit_begin":
            out.append(ParamEditBeginOp(group=group))
        elif op_type == "param_write":
            vals = _as_object_dict(item_dict.get("values", {}))
            cleaned = {str(k): _as_float(v) for k, v in vals.items()}
            out.append(ParamWriteOp(type="param_write", group=group, values=cleaned))
        elif op_type == "param_cancel":
            out.append(ParamCancelOp(group=group))
    return out


def coerce_param_ops(ops: Any) -> List[ParamOp]:
    """Coerce a mixed/legacy param-ops container into canonical ParamOp objects."""
    if ops is None or not isinstance(ops, list):
        return []

    out: List[ParamOp] = []
    for item in ops:
        if isinstance(item, (ParamEditBeginOp, ParamWriteOp, ParamCancelOp)):
            out.append(item)
            continue
        if isinstance(item, dict):
            out.extend(decode_param_ops([item]))
    return out


@dataclass(frozen=True)
class CommandFrame:
    tick: int
    t_s: float
    estop: bool
    fault: bool
    core_mode: str
    axes: Dict[str, AxisSetpoint]
    intent: bool = True
    resync: bool = False
    gui_not_halt: bool = False

    estop_reset: bool = False
    param_ops: List[ParamOp] = field(default_factory=_new_param_ops_list)
    lifetick_echo: Dict[str, int] = field(default_factory=_new_str_int_dict)
    resync_by_axis: Dict[str, bool] = field(default_factory=_new_str_bool_dict)
    main_reset_by_axis: Dict[str, bool] = field(default_factory=_new_str_bool_dict)
    guider_reset_by_axis: Dict[str, bool] = field(default_factory=_new_str_bool_dict)
