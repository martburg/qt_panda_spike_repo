from __future__ import annotations

"""Meta/heartbeat/sample intents.

Split out of core/intents.py to reduce merge conflicts and keep intent families
cohesive. The public surface remains re-exported from core/intents.py.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class JoyStateUpdate:
    """Atomic joystick state sample."""

    type: Literal["joy_state_update"] = "joy_state_update"
    deadman: bool = False
    select_hip: bool = False
    soll_speed: float = 0.0


@dataclass(frozen=True)
class EchoLifeTick:
    """Carry a UI-originated heartbeat value through Core to be mirrored by DenSi."""

    type: Literal["echo_lifetick"] = "echo_lifetick"
    axis_id: str = ""
    value: int = 0
    hip_id: str = ""
