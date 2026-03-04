"""Rig/parameter intents.

Split out of core/intents.py to reduce merge conflicts and keep intent families
cohesive. The public surface remains re-exported from core/intents.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal

ParamGroup = Literal["pos", "vel", "filter", "guider"]


@dataclass(frozen=True)
class ParamEditBegin:
    """Prime the device to accept parameter writes for a parameter group."""

    type: Literal["param_edit_begin"] = "param_edit_begin"
    axis_id: str = ""
    hip_id: str = ""
    group: ParamGroup = "pos"
    req_id: str = ""
    session_id: str = ""


@dataclass(frozen=True)
class ParamWrite:
    """Write one or more parameters (key->float) within a group."""

    type: Literal["param_write"] = "param_write"
    axis_id: str = ""
    hip_id: str = ""
    group: ParamGroup = "pos"
    values: Dict[str, float] = field(default_factory=dict)
    req_id: str = ""
    session_id: str = ""


@dataclass(frozen=True)
class ParamCancel:
    """Cancel an in-progress edit session for a parameter group."""

    type: Literal["param_cancel"] = "param_cancel"
    axis_id: str = ""
    hip_id: str = ""
    group: ParamGroup = "pos"
    req_id: str = ""
    session_id: str = ""
