from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from steuerung3d.core.mode import Mode


@dataclass
class AxisState:
    # --- axis type discriminator ---
    kind: str = "generic" 
    # --- measured (common surface) ---
    pos: float = 0.0
    vel: float = 0.0
    enabled: bool = False
    fault: bool = False

    # --- kind-specific full telemetry (opaque to most of core) ---
    tel: Optional[object] = None

    # extra free-form info (keep)
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AxisCommandState:
    # --- commanded (core wants) ---
    enable: bool = False
    vel: float = 0.0


@dataclass
class MachineState:
    """
    Single source of truth.
    """
    tick: int = 0
    t_s: float = 0.0

    mode: Mode = Mode.IDLE

    axes: Dict[str, AxisState] = field(default_factory=dict)
    axis_cmd: Dict[str, AxisCommandState] = field(default_factory=dict)
    axis_fsm: Dict[str, Any] = field(default_factory=dict)   # runtime objects (AxisFSM)

    # high-level health/safety flags (v0.1)
    estop: bool = False
    fault: bool = False

    def ensure_axis(self, axis_id: str) -> AxisState:
        if axis_id not in self.axes:
            self.axes[axis_id] = AxisState()
        return self.axes[axis_id]

    def ensure_axis_cmd(self, axis_id: str) -> AxisCommandState:
        if axis_id not in self.axis_cmd:
            self.axis_cmd[axis_id] = AxisCommandState()
        return self.axis_cmd[axis_id]