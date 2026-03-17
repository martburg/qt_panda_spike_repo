from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.command_frame import ParamOp
from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.rig_types import DensiRuntime, RecoverPlan, RigMode, RigSyncConfig


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
class AxisControl:
    """Convenience bundle for per-axis state.

    This is a structural refactor to "concentrate the model" without changing
    existing public fields. The legacy ``axes`` and ``axis_cmd`` dicts remain the
    canonical access paths for most code, but they are now backed by the same
    per-axis objects stored in ``axis_ctl``.
    """

    measured: AxisState = field(default_factory=AxisState)
    cmd: AxisCommandState = field(default_factory=AxisCommandState)


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

    # DenSi runtime registry (core is the authority).
    densi_registry: Dict[str, DensiRuntime] = field(default_factory=dict)

    # Rig workflow (core-local; published via telemetry for UI/debug)
    rig_mode: RigMode = RigMode.DISCOVERY
    rig_sync_config: RigSyncConfig = field(default_factory=RigSyncConfig)
    rig_recover_plan: RecoverPlan = field(default_factory=RecoverPlan)
    rig_last_good: Dict[str, Any] = field(default_factory=dict)
    rig_recover_timeout_ticks: int = 400

    axes: Dict[str, AxisState] = field(default_factory=dict)
    axis_cmd: Dict[str, AxisCommandState] = field(default_factory=dict)

    # Bundled per-axis view (structural): axis_id -> AxisControl
    axis_ctl: Dict[str, AxisControl] = field(default_factory=dict)

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
    # Per-axis one-shot request (canonical)
    estop_reset_req_by_axis: Dict[str, bool] = field(default_factory=dict)
    # Policy diagnostics: denied reset requests per axis
    estop_reset_denied_count_by_axis: Dict[str, int] = field(default_factory=dict)

    # ReSync pulse (clears cut marker latches / recover flow), per axis.
    resync_req_by_axis: Dict[str, bool] = field(default_factory=dict)

    # Main/guider amplifier reset pulses (one-shot), emitted via ControlIN/GuideControlUI bitfields
    main_reset_req_by_axis: Dict[str, bool] = field(default_factory=dict)
    guider_reset_req_by_axis: Dict[str, bool] = field(default_factory=dict)

    estop_status_word: int = 0  # NEW: measured bitfield

    # --- parameters (axis-agnostic v0.1) ---
    # Measured/confirmed by device (via telemetry):
    param_edit_active: bool = False
    param_edit_group: str = ""
    params: Dict[str, float] = field(default_factory=dict)

    # Pending ops to be sent on the next command frame (core-side only).
    # Per-axis storage is canonical; param intents without axis_id are rejected.
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
    control_mode: str = ""

    # --- core mode aggregation (Stage 2) ---
    core_mode: CoreMode = CoreMode.ESTOP
    core_blocked_by: list[object] = field(default_factory=list)
    core_axis_gate: Dict[str, Dict[str, object]] = field(default_factory=dict)
    core_motion_allowed: bool = False

    def clear_one_shots(self) -> None:
        """Clear one-shot request fields after they have been emitted once.

        Semantic policy (2026-03-17):
        - Reset/resync one-shots are per-axis only via ``*_by_axis`` maps.
        - Parameter ops are per-axis only; axis-less param intents are rejected at the boundary.
        """

        # Reset / resync pulses (one-shot)
        self.estop_reset_req_by_axis.clear()

        self.resync_req_by_axis.clear()

        self.main_reset_req_by_axis.clear()
        self.guider_reset_req_by_axis.clear()

        # Parameter ops are one-shot as well (UI can re-issue if needed)
        self.pending_param_ops_by_axis.clear()

    def clear_transients(self) -> None:
        """Clear transient/one-shot state after a full engine tick.

        This consolidates the end-of-tick cleanup into a single supported write-path.
        """

        self.clear_one_shots()
        self.core_acks.clear()

    def ensure_axis(self, axis_id: str) -> AxisState:
        axis_id = normalize_axis_id(axis_id)
        if axis_id not in self.axis_ctl:
            self.axis_ctl[axis_id] = AxisControl()
        ctl = self.axis_ctl[axis_id]
        # Keep legacy dicts backed by the same objects.
        self.axes[axis_id] = ctl.measured
        self.axis_cmd[axis_id] = ctl.cmd
        return ctl.measured

    def ensure_axis_cmd(self, axis_id: str) -> AxisCommandState:
        axis_id = normalize_axis_id(axis_id)
        self.ensure_axis(axis_id)
        return self.axis_cmd[axis_id]

    def axis_owner(self, axis_id: str) -> str:
        """Best-effort owner resolution (claim first, then lease)."""

        axis_id = normalize_axis_id(axis_id)
        if not axis_id:
            return ""

        owner = str((self.axis_claims or {}).get(axis_id, "") or "")
        if owner:
            return owner

        holders = list((self.lease_axis_holders or {}).get(axis_id, []) or [])
        return str(holders[0]) if holders else ""

    def claim_owner(self, axis_id: str) -> str:
        """Return current claim owner for *axis_id* (empty if none)."""

        axis_id = normalize_axis_id(axis_id)
        if not axis_id:
            return ""
        return str((self.axis_claims or {}).get(axis_id, "") or "")

    def is_claim_owner(self, axis_id: str, hip_id: str) -> bool:
        """Return whether *hip_id* matches the claim owner for *axis_id*."""

        axis_id = normalize_axis_id(axis_id)
        hip_id = str(hip_id or "")
        if not axis_id or not hip_id:
            return False
        owner = self.claim_owner(axis_id)
        return bool(owner) and (owner == hip_id)

    def _sync_densi_claim_surface(self, axis_id: str, hip_id: str) -> None:
        """Mirror claim ownership onto the DenSi runtime registry."""

        axis_id = normalize_axis_id(axis_id)
        if not axis_id:
            return
        d = self.densi_registry.get(axis_id)
        if d is None:
            d = DensiRuntime(device_id=axis_id)
            self.densi_registry[axis_id] = d
        d.claimed_by_hip = str(hip_id or "")

    def set_axis_claim(self, axis_id: str, hip_id: str) -> None:
        """Set exclusive control claim for *axis_id*.

        This is the supported write-path for ``axis_claims`` in production code
        (intent handlers). Tests may use it for setup as well.

        Notes:
        - Ensures the axis exists (so downstream logic can rely on ``ensure_axis``).
        - Mirrors ownership into ``densi_registry`` so HiP discovery/UI can use a
          single authoritative surface for attachability.
        - Does not perform policy checks; callers are responsible (e.g. ClaimAxis handler).
        """
        axis_id = normalize_axis_id(axis_id)
        hip_id = str(hip_id or "")
        if not axis_id or not hip_id:
            return
        self.ensure_axis(axis_id)
        self.axis_claims[axis_id] = hip_id
        self._sync_densi_claim_surface(axis_id, hip_id)

    def clear_axis_claim(self, axis_id: str, *, hip_id: str | None = None) -> None:
        """Clear exclusive control claim for *axis_id*.

        If *hip_id* is provided, the claim is only cleared if it matches the
        current claim owner.
        """
        axis_id = normalize_axis_id(axis_id)
        if not axis_id:
            return
        if hip_id is not None:
            hip_id = str(hip_id or "")
            if hip_id and self.claim_owner(axis_id) != hip_id:
                return
        self.axis_claims.pop(axis_id, None)
        self._sync_densi_claim_surface(axis_id, "")

    def clear_claims_for_hip(self, hip_id: str) -> list[str]:
        """Release all claims currently owned by *hip_id* and return them."""

        hip_id = str(hip_id or "")
        if not hip_id:
            return []
        released = [axis_id for axis_id, owner in dict(self.axis_claims).items() if owner == hip_id]
        for axis_id in released:
            self.clear_axis_claim(axis_id, hip_id=hip_id)
        return sorted(released)
