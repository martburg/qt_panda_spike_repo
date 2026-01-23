from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any

from steuerung3d.core.command_frame import ParamOp

from steuerung3d.core.mode import Mode


@dataclass
class AxisState:
    # --- measured (what the device reports / sim produces) ---
    pos: float = 0.0
    vel: float = 0.0
    enabled: bool = False
    fault: bool = False
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

    # high-level health/safety flags (v0.1)
    estop: bool = False
    fault: bool = False
    estop_reset_req: bool = False

    estop_status_word: int = 0   # NEW: measured bitfield

    # --- parameters (axis-agnostic v0.1) ---
    # Measured/confirmed by device (via telemetry):
    param_edit_active: bool = False
    param_edit_group: str = ""
    params: Dict[str, float] = field(default_factory=dict)

    # Pending ops to be sent on the next command frame (core-side only):
    pending_param_ops: list[ParamOp] = field(default_factory=list)


    def ensure_axis(self, axis_id: str) -> AxisState:
        if axis_id not in self.axes:
            self.axes[axis_id] = AxisState()
        return self.axes[axis_id]

    def ensure_axis_cmd(self, axis_id: str) -> AxisCommandState:
        if axis_id not in self.axis_cmd:
            self.axis_cmd[axis_id] = AxisCommandState()
        return self.axis_cmd[axis_id]