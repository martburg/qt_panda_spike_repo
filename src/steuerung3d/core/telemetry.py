# src/steuerung3d/core/telemetry.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from steuerung3d.core.mode import Mode
from steuerung3d.core.core_mode import core_mode_value
from steuerung3d.core.state import AxisState, MachineState
from steuerung3d.core.param_registry import eps_for_param
from steuerung3d.core.joy_state import JoyState
from steuerung3d.common.staleness import age_ticks, is_stale
from steuerung3d.core.rig_logic import note_densi_seen

@dataclass(frozen=True)
class AxisTelemetry:
    # measured
    pos: float
    vel: float
    enabled: bool
    fault: bool

    # commanded (what core wants, echoed for UI/HiP)
    vel_cmd: float = 0.0
    enable_cmd: bool = False


    # legacy/layer-0 diagnostics (optional on the wire)
    device_tick: int = 0          # PLC/device lifetick (legacy LifetickUItx)
    lifetick_rx: int = 0          # echoed tick seen at device (legacy LifetickUIrx), if available
    lifetick_age: int = 0         # (device_tick - lifetick_rx) mod 65536, if available
    status_word: int = 0          # legacy Status (drive/main amp)
    guide_status_word: int = 0    # legacy GuideStatus (slave/guider amp)




@dataclass(frozen=True)
class DensiTelemetry:
    device_id: str
    online: bool
    claimed_by_hip: str = ""
    participating: bool = False
    anchor_xyz: tuple[float, float, float] | None = None
    last_seen_age_ticks: int = 0

@dataclass(frozen=True)
class TelemetrySnapshot:
    tick: int
    t_s: float
    mode: str
    core_mode: str
    estop: bool
    fault: bool
    axes: Dict[str, AxisTelemetry]

    # Rig workflow
    rig_mode: str = "DISCOVERY"
    densis: Dict[str, DensiTelemetry] = field(default_factory=dict)

    # Leases (Core-owned authority surface)
    lease_rig: str = ""
    lease_axis: Dict[str, list[str]] = field(default_factory=dict)
    lease_rig_holder: str = ""
    lease_axis_holders: Dict[str, list[str]] = field(default_factory=dict)
    lease_denial_reason: str = ""

    # NEW
    estop_status_word: int = 0

    # Parameters (axis-agnostic v0.1)
    param_edit_active: bool = False
    param_edit_group: str = ""
    params: Dict[str, float] = field(default_factory=dict)

    # Raw PLC uplink payload (so HiP can decide what to use without changing decode again)
    plc_uplink_fields: Dict[str, str] = field(default_factory=dict)  # base fields (pre-EOD)
    plc_uplink_tail: Dict[str, str] = field(default_factory=dict)    # tail fields (post-EOD)

    # HIP<->Core transactional acks (one-shot)
    core_acks: list[str] = field(default_factory=list)

    # Observed param commit status (Core-side inference from DenSi telemetry)
    param_commit_req_id: str = ""
    param_commit_group: str = ""
    param_commit_status: str = "idle"  # idle|pending|applied|timeout|cancelled
    param_commit_age_ticks: int = 0
    param_commit_unmatched: list[str] = field(default_factory=list)

    # Joystick state (UI-only; not used for device telemetry)
    joy: JoyState = field(default_factory=JoyState)

    @classmethod
    def from_state(cls, state: MachineState) -> "TelemetrySnapshot":
        axes = {
            axis_id: AxisTelemetry(
                pos=float(ax.pos),
                vel=float(ax.vel),
                enabled=bool(ax.enabled),
                fault=bool(ax.fault),
                vel_cmd=float(getattr(state.axis_cmd.get(axis_id, None), 'vel', 0.0)) if hasattr(state, 'axis_cmd') else 0.0,
                enable_cmd=bool(getattr(state.axis_cmd.get(axis_id, None), 'enable', False)) if hasattr(state, 'axis_cmd') else False,
                device_tick=int(getattr(ax, 'meta', {}).get('device_tick', 0)) & 0xFFFF,
                lifetick_rx=int(getattr(ax, 'meta', {}).get('lifetick_rx', 0)) & 0xFFFF,
                lifetick_age=int(getattr(ax, 'meta', {}).get('lifetick_age', 0)) & 0xFFFF,
                status_word=int(getattr(ax, 'meta', {}).get('status_word', 0)),
                guide_status_word=int(getattr(ax, 'meta', {}).get('guide_status_word', 0)),
            )
            for axis_id, ax in state.axes.items()
        }

        densis = {}
        try:
            offline_after = int(getattr(state, "densi_offline_after_ticks", 200))
            for dev_id, d in dict(getattr(state, "densi_registry", {})).items():
                last_seen = int(getattr(d, "last_seen_core_tick", -1))
                if last_seen < 0:
                    age = int(offline_after) + 1
                    online = False
                else:
                    age = int(age_ticks(int(state.tick), int(last_seen)) or 0)
                    online = not is_stale(int(state.tick), int(last_seen), int(offline_after) + 1)
                densis[str(dev_id)] = DensiTelemetry(
                    device_id=str(dev_id),
                    online=bool(online),
                    claimed_by_hip=str(getattr(d, "claimed_by_hip", "")),
                    participating=bool(getattr(d, "participating", False)),
                    anchor_xyz=getattr(d, "anchor_xyz", None),
                    last_seen_age_ticks=int(age),
                )
        except Exception:
            densis = {}

        lease_rig = str(getattr(state, "lease_rig", ""))
        lease_axis: Dict[str, list[str]] = {}
        lease_axis_holders: Dict[str, list[str]] = {}
        try:
            lease_axis_holders = {
                str(k): [str(x) for x in list(v)]
                for k, v in dict(getattr(state, "lease_axis_holders", {}) or {}).items()
                if isinstance(v, (list, tuple))
            }
        except Exception:
            lease_axis_holders = {}

        if lease_axis_holders:
            lease_axis = dict(lease_axis_holders)
        else:
            try:
                claims = dict(getattr(state, "axis_claims", {}) or {})
                for axis_id, hip_id in claims.items():
                    if hip_id:
                        lease_axis[str(axis_id)] = [str(hip_id)]
            except Exception:
                lease_axis = {}

        return cls(
            tick=int(state.tick),
            t_s=float(state.t_s),
            mode=state.mode.value if hasattr(state.mode, "value") else str(state.mode),
            core_mode=core_mode_value(getattr(state, "core_mode", "")),
            estop=bool(state.estop),
            fault=bool(state.fault),
            axes=axes,
            rig_mode=str(getattr(state, "rig_mode", "DISCOVERY")),
            densis=densis,
            lease_rig=lease_rig,
            lease_axis=lease_axis,
            lease_rig_holder=lease_rig,
            lease_axis_holders=lease_axis_holders if lease_axis_holders else dict(lease_axis),
            lease_denial_reason=str(getattr(state, "lease_last_denial_reason", "")),
            estop_status_word=int(getattr(state, "estop_status_word", 0)),
            param_edit_active=bool(getattr(state, "param_edit_active", False)),
            param_edit_group=str(getattr(state, "param_edit_group", "")),
            params=dict(getattr(state, "params", {})),
            core_acks=list(getattr(state, "core_acks", [])),
            param_commit_req_id=str(getattr(state, "param_commit_req_id", "")),
            param_commit_group=str(getattr(state, "param_commit_group", "")),
            param_commit_status=str(getattr(state, "param_commit_status", "idle")),
            param_commit_age_ticks=int(getattr(state, "param_commit_observed_ticks", 0) if str(getattr(state, "param_commit_status", "idle")) in ("pending", "timeout") else 0),
            param_commit_unmatched=list(getattr(state, "param_commit_unmatched", [])),
            joy=getattr(state, "joy", JoyState()),
        )


def _update_param_commit_observation(state: MachineState, device_tick: int) -> None:
    """Update observed param commit state using device telemetry params.

    We treat a ParamWrite as applied once telemetry.params matches desired values for
    2 consecutive *new* device telemetry ticks.

    Timeout advances only on new device ticks (if telemetry tick stalls, timeout pauses).
    """
    if state.param_commit_status != "pending":
        return

    dtick = int(device_tick)
    last = int(getattr(state, "param_commit_last_device_tick", -1))
    if dtick == last:
        return
    state.param_commit_last_device_tick = dtick
    state.param_commit_observed_ticks = int(getattr(state, "param_commit_observed_ticks", 0)) + 1

    desired = dict(getattr(state, "param_commit_desired", {}))
    if not desired:
        state.param_commit_status = "applied"
        state.param_commit_unmatched = []
        return

    params = dict(getattr(state, "params", {}))
    unmatched: list[str] = []
    for k, want in desired.items():
        if k not in params:
            unmatched.append(k)
            continue
        try:
            eps = eps_for_param(k, 1e-6)
            if abs(float(params[k]) - float(want)) > eps:
                unmatched.append(k)
        except Exception:
            unmatched.append(k)

    state.param_commit_unmatched = unmatched

    if not unmatched:
        state.param_commit_match_streak = int(getattr(state, "param_commit_match_streak", 0)) + 1
        if state.param_commit_match_streak >= 2:
            state.param_commit_status = "applied"
            return
    else:
        state.param_commit_match_streak = 0

    if int(getattr(state, "param_commit_observed_ticks", 0)) >= int(getattr(state, "param_commit_timeout_ticks", 40)):
        state.param_commit_status = "timeout"


def apply_measured_snapshot(state: MachineState, snap: TelemetrySnapshot) -> None:
    """Apply a device/DenSi measured snapshot to MachineState.

    Important: measured snapshots must NOT override core-owned workflow state such as
    the mode/state-machine, or parameter edit session flags. They should only update
    measured values (pos/vel, estop word, and measured params).
    """
    # Core mode is driven by intents + state machine; ignore snap.mode from PLC telemetry.
    state.estop = bool(getattr(snap, "estop", False))
    state.fault = bool(getattr(snap, "fault", False))

    # Carry the raw estop status word through the core for bit-wrangling UI + reset_able.
    state.estop_status_word = int(getattr(snap, "estop_status_word", 0))

    # Measured parameters (optional on the wire). Never clear on empty.
    incoming_params = dict(getattr(snap, "params", {}) or {})
    if incoming_params:
        for k, v in incoming_params.items():
            try:
                state.params[str(k)] = float(v)
            except Exception:
                continue

    # Observe parameter commit acceptance by comparing requested values to measured params.
    _update_param_commit_observation(state, int(getattr(snap, "tick", 0)))

    for axis_id, ax_t in snap.axes.items():
        ax: AxisState = state.ensure_axis(axis_id)
        note_densi_seen(state, axis_id, device_tick=int(getattr(snap, "tick", 0)))
        ax.pos = float(ax_t.pos)
        ax.vel = float(ax_t.vel)
        ax.enabled = bool(ax_t.enabled)
        ax.fault = bool(ax_t.fault)

        # Carry device-side lifetick through the core (legacy LifetickUItx analogue).
        # Needed for UI TimeTick (delta between successive received device ticks).
        ax.meta["device_tick"] = int(getattr(ax_t, "device_tick", 0)) & 0xFFFF
        ax.meta["lifetick_rx"] = int(getattr(ax_t, "lifetick_rx", 0)) & 0xFFFF
        ax.meta["lifetick_age"] = int(getattr(ax_t, "lifetick_age", 0)) & 0xFFFF
        ax.meta["status_word"] = int(getattr(ax_t, "status_word", 0))
        ax.meta["guide_status_word"] = int(getattr(ax_t, "guide_status_word", 0))

