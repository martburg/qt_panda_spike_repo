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


    # --- HIP<->Core transactional acks (axis-agnostic parameter ops) ---
    # One-shot ack list emitted in TelemetrySnapshot, then cleared after publish.
    core_acks: list[str] = field(default_factory=list)

    # Deduplication of transactional intents: req_id -> last_seen_tick
    seen_req_ids: Dict[str, int] = field(default_factory=dict)

    # --- Observed parameter commit status (Core->DenSi is not transactional) ---
    # DenSi/PLC is considered "semi-frozen": we cannot rely on ACKs.
    # Instead, we treat a parameter write as "applied" once the device's
    # telemetry reports params matching the requested values (within tolerance).
    param_commit_req_id: str = ""
    param_commit_group: str = ""
    param_commit_status: str = "idle"  # idle|pending|applied|timeout|cancelled
    param_commit_start_tick: int = 0
    param_commit_desired: Dict[str, float] = field(default_factory=dict)
    param_commit_unmatched: list[str] = field(default_factory=list)
    # Default: ~2s at 50ms/tick (CoreEngine default polling). Adjust as needed.
    param_commit_timeout_ticks: int = 40


    def ensure_axis(self, axis_id: str) -> AxisState:
        if axis_id not in self.axes:
            self.axes[axis_id] = AxisState()
        return self.axes[axis_id]

    def ensure_axis_cmd(self, axis_id: str) -> AxisCommandState:
        if axis_id not in self.axis_cmd:
            self.axis_cmd[axis_id] = AxisCommandState()
        return self.axis_cmd[axis_id]