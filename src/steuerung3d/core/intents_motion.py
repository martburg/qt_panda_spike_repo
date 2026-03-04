"""Operator motion intents.

Split out of core/intents.py to reduce merge conflicts and keep intent families
cohesive. The public surface remains re-exported from core/intents.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Keep "type" as an explicit discriminant: easy for codecs + pattern matching.


@dataclass(frozen=True)
class EnableAxis:
    type: Literal["enable_axis"] = "enable_axis"
    axis_id: str = ""
    enable: bool = True
    hip_id: str = ""


@dataclass(frozen=True)
class JogAxis:
    type: Literal["jog_axis"] = "jog_axis"
    axis_id: str = ""
    vel: float = 0.0
    hip_id: str = ""


ControlMode = Literal["setup_manual", "sync_live"]


@dataclass(frozen=True)
class SetControlMode:
    type: Literal["set_control_mode"] = "set_control_mode"
    mode: ControlMode = "setup_manual"


@dataclass(frozen=True)
class JogWinch:
    type: Literal["jog_winch"] = "jog_winch"
    winch_id: str = ""
    rate: float = 0.0
    hip_id: str = ""


@dataclass(frozen=True)
class JogCartesian:
    type: Literal["jog_cartesian"] = "jog_cartesian"
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    hip_id: str = ""


@dataclass(frozen=True)
class SmoothStop:
    type: Literal["smooth_stop"] = "smooth_stop"
