# src/steuerung3d/core/telemetry.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from steuerung3d.core.mode import Mode
from steuerung3d.core.state import AxisState, MachineState

@dataclass(frozen=True)
class AxisTelemetry:
    pos: float
    vel: float
    enabled: bool
    fault: bool

@dataclass(frozen=True)
class TelemetrySnapshot:
    tick: int
    t_s: float
    mode: str
    estop: bool
    fault: bool
    axes: Dict[str, AxisTelemetry]

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
            )
            for axis_id, ax in state.axes.items()
        }
        return cls(
            tick=int(state.tick),
            t_s=float(state.t_s),
            mode=state.mode.value if hasattr(state.mode, "value") else str(state.mode),
            estop=bool(state.estop),
            fault=bool(state.fault),
            axes=axes,
            estop_status_word=int(getattr(state, "estop_status_word", 0)),
            param_edit_active=bool(getattr(state, "param_edit_active", False)),
            param_edit_group=str(getattr(state, "param_edit_group", "")),
            params=dict(getattr(state, "params", {})),
            core_acks=list(getattr(state, "core_acks", [])),
            param_commit_req_id=str(getattr(state, "param_commit_req_id", "")),
            param_commit_group=str(getattr(state, "param_commit_group", "")),
            param_commit_status=str(getattr(state, "param_commit_status", "idle")),
            param_commit_age_ticks=int(
                int(getattr(state, "tick", 0)) - int(getattr(state, "param_commit_start_tick", 0))
                if str(getattr(state, "param_commit_status", "idle")) in ("pending", "timeout")
                else 0
            ),
            param_commit_unmatched=list(getattr(state, "param_commit_unmatched", [])),
        )


def _update_param_commit_observation(state: MachineState) -> None:
    """Advance state.param_commit_status based on currently measured state.params."""
    if state.param_commit_status != "pending":
        return
    desired = dict(getattr(state, "param_commit_desired", {}))
    if not desired:
        # nothing to validate
        state.param_commit_status = "applied"
        state.param_commit_unmatched = []
        return

    params = dict(getattr(state, "params", {}))
    eps = 1e-6

    unmatched: list[str] = []
    for k, want in desired.items():
        if k not in params:
            unmatched.append(k)
            continue
        got = params[k]
        try:
            if abs(float(got) - float(want)) > eps:
                unmatched.append(k)
        except Exception:
            # type mismatch: treat as unmatched
            unmatched.append(k)

    state.param_commit_unmatched = unmatched
    if not unmatched:
        state.param_commit_status = "applied"
        return

    age = int(state.tick) - int(state.param_commit_start_tick)
    if age >= int(getattr(state, "param_commit_timeout_ticks", 40)):
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
    _update_param_commit_observation(state)

    for axis_id, ax_t in snap.axes.items():
        ax: AxisState = state.ensure_axis(axis_id)
        ax.pos = float(ax_t.pos)
        ax.vel = float(ax_t.vel)
        ax.enabled = bool(ax_t.enabled)
        ax.fault = bool(ax_t.fault)
