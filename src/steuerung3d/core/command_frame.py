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


def coerce_param_ops(ops: Any) -> List[ParamOp]:
    """Coerce a mixed/legacy param-ops container into canonical ParamOp objects.

    In the codebase, param_ops should be a list[ParamOp]. Historically,
    some paths used JSON-like dicts (e.g. recordings, older emitters).

    This helper centralizes tolerance so consumers don't need ad-hoc
    getattr/op.get branches. Unknown items are ignored.
    """
    if ops is None:
        return []
    if not isinstance(ops, list):
        return []

    out: List[ParamOp] = []
    for item in ops:
        if isinstance(item, (ParamEditBeginOp, ParamWriteOp, ParamCancelOp)):
            out.append(item)
            continue
        if isinstance(item, dict):
            # decode_param_ops expects a list of dicts
            out.extend(decode_param_ops([item]))
            continue
        # ignore unknown
    return out


@dataclass(frozen=True)
class CommandFrame:
    tick: int
    t_s: float
    estop: bool          # legacy/unused for authority (keep for now)
    fault: bool
    mode: str
    axes: Dict[str, AxisSetpoint]
    # --- legacy downlink knobs (TwinCAT PLC protocol) ---
    # Keep defaults so existing callers/tests remain stable.
    # intent: controller "claim" bit (PLC expects "True"/"False" string)
    intent: bool = True
    # resync: legacy ReSync signal (clears cut markers / recover flow)
    resync: bool = False
    # gui_not_halt: legacy GUI Not-Halt input (placeholder until verified)
    gui_not_halt: bool = False

    estop_reset: bool  = False  # momentary request to clear device latch
    # NEW: parameter editing/writing operations (axis-agnostic v0.1)
    param_ops: List[ParamOp] = field(default_factory=list)

    # NEW (optional): UI-originating livetick echo values by axis.
    # Keep empty by default so existing regression fingerprints stay stable.
    lifetick_echo: Dict[str, int] = field(default_factory=dict)
