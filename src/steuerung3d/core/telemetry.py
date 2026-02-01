# src/steuerung3d/core/telemetry.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from steuerung3d.core.mode import Mode
from steuerung3d.core.state import AxisState, MachineState
from steuerung3d.core.param_registry import eps_for_param

@dataclass(frozen=True)
class AxisTelemetry:
    pos: float
    vel: float
    enabled: bool
    fault: bool

    # PLC watchdog / comms timing (optional).
    # These are carried through telemetry so UIs can show link health.
    lifetick_tx: Optional[int] = None
    lifetick_rx: Optional[int] = None
    timetick_ms: Optional[int] = None



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
    estop: bool
    fault: bool
    axes: Dict[str, AxisTelemetry]

    # Rig workflow
    rig_mode: str = "DISCOVERY"
    densis: Dict[str, DensiTelemetry] = field(default_factory=dict)

    # NEW
    estop_status_word: int = 0

    # Parameters (axis-agnostic v0.1)
    param_edit_active: bool = False
    param_edit_group: str = ""
    params: Dict[str, float] = field(default_factory=dict)

    # HIP<->Core transactional acks (one-shot)
    core_acks: list[str] = field(default_factory=list)

    # Observed param commit status (Core-side inference from DenSi telemetry)
    param_commit_req_id: str = ""
    param_commit_group: str = ""
    param_commit_status: str = "idle"  # idle|pending|applied|timeout|cancelled
    param_commit_age_ticks: int = 0
    param_commit_unmatched: list[str] = field(default_factory=list)

    @classmethod
    def from_state(cls, state: MachineState) -> "TelemetrySnapshot":
        axes = {
            axis_id: AxisTelemetry(
                pos=float(ax.pos),
                vel=float(ax.vel),
                enabled=bool(ax.enabled),
                fault=bool(ax.fault),
                lifetick_tx=(
                    int(ax.meta.get("lifetick_tx"))
                    if isinstance(getattr(ax, "meta", None), dict) and "lifetick_tx" in ax.meta
                    else None
                ),
                lifetick_rx=(
                    int(ax.meta.get("lifetick_rx"))
                    if isinstance(getattr(ax, "meta", None), dict) and "lifetick_rx" in ax.meta
                    else None
                ),
                timetick_ms=(
                    int(ax.meta.get("timetick_ms"))
                    if isinstance(getattr(ax, "meta", None), dict) and "timetick_ms" in ax.meta
                    else None
                ),
            )
            for axis_id, ax in state.axes.items()
        }

        densis = {}
        try:
            offline_after = int(getattr(state, "densi_offline_after_ticks", 40))
            for dev_id, d in dict(getattr(state, "densi_registry", {})).items():
                age = int(state.tick) - int(getattr(d, "last_seen_core_tick", -10**9))
                online = age <= offline_after
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

        return cls(
            tick=int(state.tick),
            t_s=float(state.t_s),
            mode=state.mode.value if hasattr(state.mode, "value") else str(state.mode),
            estop=bool(state.estop),
            fault=bool(state.fault),
            axes=axes,
            rig_mode=str(getattr(state, "rig_mode", "DISCOVERY")),
            densis=densis,
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
    state.mode = Mode(snap.mode) if isinstance(snap.mode, str) else snap.mode
    state.estop = bool(snap.estop)
    state.fault = bool(snap.fault)

    # NEW: carry the word through the core
    state.estop_status_word = int(getattr(snap, "estop_status_word", 0))

    # parameters (optional on the wire)
    state.param_edit_active = bool(getattr(snap, "param_edit_active", False))
    state.param_edit_group = str(getattr(snap, "param_edit_group", ""))
    state.params = dict(getattr(snap, "params", {}))

    # Observe parameter commit acceptance by comparing requested values to measured params.
    _update_param_commit_observation(state, int(getattr(snap, "tick", 0)))

    for axis_id, ax_t in snap.axes.items():
        ax: AxisState = state.ensure_axis(axis_id)
        ax.pos = float(ax_t.pos)
        ax.vel = float(ax_t.vel)
        ax.enabled = bool(ax_t.enabled)
        ax.fault = bool(ax_t.fault)
