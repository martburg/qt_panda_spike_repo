from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Union


@dataclass(frozen=True)
class AxisSetpoint:
    enable: bool
    vel: float  # units/s (placeholder)


# -------- Parameters (axis-agnostic, v0.1) --------

ParamGroup = Literal["pos", "vel", "filter"]


@dataclass(frozen=True)
class ParamEditBeginOp:
    type: Literal["param_edit_begin"] = "param_edit_begin"
    group: ParamGroup = "pos"


@dataclass(frozen=True)
class ParamWriteOp:
    type: Literal["param_write"] = "param_write"
    group: ParamGroup = "pos"
    values: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ParamCancelOp:
    type: Literal["param_cancel"] = "param_cancel"
    group: ParamGroup = "pos"


ParamOp = Union[ParamEditBeginOp, ParamWriteOp, ParamCancelOp]


def decode_param_ops(payload: Any) -> List[ParamOp]:
    """Decode param operations from a JSON-like structure.

    We keep this tolerant: unknown ops are ignored.
    """
    if payload is None:
        return []
    if not isinstance(payload, list):
        return []

    out: List[ParamOp] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        if t == "param_edit_begin":
            out.append(ParamEditBeginOp(**item))
        elif t == "param_write":
            # ensure values is a dict[str,float]
            vals = dict(item.get("values", {}))
            cleaned = {str(k): float(v) for k, v in vals.items()}
            out.append(ParamWriteOp(type="param_write", group=item.get("group", "pos"), values=cleaned))
        elif t == "param_cancel":
            out.append(ParamCancelOp(**item))
        else:
            continue
    return out


@dataclass(frozen=True)
class CommandFrame:
    tick: int
    t_s: float
    estop: bool          # legacy/unused for authority (keep for now)
    fault: bool
    mode: str
    axes: Dict[str, AxisSetpoint]
    estop_reset: bool  = False  # NEW: momentary request to clear device latch
    # NEW: parameter editing/writing operations (axis-agnostic v0.1)
    param_ops: List[ParamOp] = field(default_factory=list)
