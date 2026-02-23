from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any

from steuerung3d.core.command_frame import ParamOp

from steuerung3d.core.mode import Mode
from steuerung3d.core.joy_state import JoyState


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

    # DenSi device offline detection.
    # Default is intentionally conservative to tolerate ~100-200ms RTT + jitter.
    # (Core tick is typically 10ms -> 200 ticks ~= 2.0s)
    densi_offline_after_ticks: int = 200

    mode: Mode = Mode.IDLE

    axes: Dict[str, AxisState] = field(default_factory=dict)
    axis_cmd: Dict[str, AxisCommandState] = field(default_factory=dict)

    # Exclusive control claims: axis_id -> hip_id (set by ClaimAxis/ReleaseAxis)
    axis_claims: Dict[str, str] = field(default_factory=dict)

    # Rig-level lease (exclusive). Core owns policy; default empty.
    lease_rig: str = ""
    # Axis leases (set-valued holders per axis)
    lease_axis_holders: Dict[str, list[str]] = field(default_factory=dict)
    # Last lease denial reason (for telemetry)
    lease_last_denial_reason: str = ""

    # high-level health/safety flags (v0.1)
    estop: bool = False
    fault: bool = False
    estop_reset_req: bool = False  # legacy/global (single-axis)
    # NEW: per-axis one-shot request (preferred for multi-axis)
    estop_reset_req_by_axis: Dict[str, bool] = field(default_factory=dict)
    # Policy diagnostics: denied reset requests per axis
    estop_reset_denied_count_by_axis: Dict[str, int] = field(default_factory=dict)

    # Legacy ReSync pulse (clears cut marker latches / recover flow)
    resync_req: bool = False  # legacy/global (single-axis)
    resync_req_by_axis: Dict[str, bool] = field(default_factory=dict)

    estop_status_word: int = 0   # NEW: measured bitfield

    # --- parameters (axis-agnostic v0.1) ---
    # Measured/confirmed by device (via telemetry):
    param_edit_active: bool = False
    param_edit_group: str = ""
    params: Dict[str, float] = field(default_factory=dict)

    # Pending ops to be sent on the next command frame (core-side only):
    pending_param_ops: list[ParamOp] = field(default_factory=list)  # legacy/global
    # NEW: per-axis pending ops (preferred for multi-axis)
    pending_param_ops_by_axis: Dict[str, list[ParamOp]] = field(default_factory=dict)


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
    # Observation bookkeeping (device tick based):
    param_commit_last_device_tick: int = -1
    param_commit_observed_ticks: int = 0
    param_commit_match_streak: int = 0
    # Default: ~2s at 50ms/tick (CoreEngine default polling). Adjust as needed.
    param_commit_timeout_ticks: int = 40

    # --- livetick echo (optional) ---
    # HI-P can emit EchoLifeTick(axis_id,value). Core stores the last value per axis
    # and forwards it via CommandFrame.lifetick_echo so DenSi/device can mirror it.
    lifetick_echo_by_axis: Dict[str, int] = field(default_factory=dict)

    # --- joystick state (UI telemetry only; used in Stage 2) ---
    joy: JoyState = field(default_factory=JoyState)


    def ensure_axis(self, axis_id: str) -> AxisState:
        if axis_id not in self.axes:
            self.axes[axis_id] = AxisState()
        return self.axes[axis_id]

    def ensure_axis_cmd(self, axis_id: str) -> AxisCommandState:
        if axis_id not in self.axis_cmd:
            self.axis_cmd[axis_id] = AxisCommandState()
        return self.axis_cmd[axis_id]