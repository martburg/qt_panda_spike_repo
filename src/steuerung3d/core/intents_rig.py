"""Rig/parameter intents.

Split out of core/intents.py to reduce merge conflicts and keep intent families
cohesive. The public surface remains re-exported from core/intents.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal

from .param_groups import ParamGroup


def _new_param_values() -> Dict[str, float]:
    return {}


def _require_param_axis_id(axis_id: str, *, intent_type: str) -> str:
    axis = str(axis_id or "").strip()
    if not axis:
        raise ValueError(f"{intent_type} requires non-empty axis_id")
    return axis


@dataclass(frozen=True)
class ParamEditBegin:
    """Prime the device to accept parameter writes for a parameter group."""

    type: Literal["param_edit_begin"] = "param_edit_begin"
    axis_id: str = ""
    hip_id: str = ""
    group: ParamGroup = "pos"
    req_id: str = ""
    session_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "axis_id",
            _require_param_axis_id(self.axis_id, intent_type=self.type),
        )


@dataclass(frozen=True)
class ParamWrite:
    """Write one or more parameters (key->float) within a group."""

    type: Literal["param_write"] = "param_write"
    axis_id: str = ""
    hip_id: str = ""
    group: ParamGroup = "pos"
    values: Dict[str, float] = field(default_factory=_new_param_values)
    req_id: str = ""
    session_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "axis_id",
            _require_param_axis_id(self.axis_id, intent_type=self.type),
        )


@dataclass(frozen=True)
class ParamCancel:
    """Cancel an in-progress edit session for a parameter group."""

    type: Literal["param_cancel"] = "param_cancel"
    axis_id: str = ""
    hip_id: str = ""
    group: ParamGroup = "pos"
    req_id: str = ""
    session_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "axis_id",
            _require_param_axis_id(self.axis_id, intent_type=self.type),
        )
