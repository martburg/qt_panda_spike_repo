"""HiP engine step pipeline (extracted).

No semantic changes intended; this is a mechanical extraction from `engine.py`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for type checking; avoids runtime import cycles.
    from .engine import HipEngine

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.intents import (
    Intent,
    RequestEstopReset,
    RequestGuiderReset,
    RequestMainReset,
    RequestResync,
)
from steuerung3d.core.joy_state import JoyState

from .intent_policy import gate_motion_intents
from .param_ui import run_param_txn
from .step_context import build_step_context
from .step_phase_motion import compute_motion_phase, project_local_joy
from .step_phase_presentation import compute_presentation_phase
from .types import HipStepInputs, HipStepResult


def step(*, engine: "HipEngine", inputs: HipStepInputs) -> HipStepResult:
    """Run one HiP engine tick."""
    self = engine

    ctx = build_step_context(engine=self, inputs=inputs)

    snap = ctx.snap
    ui = ctx.ui
    hip_id = ctx.hip_id
    axis_ids = ctx.axis_ids
    axes = snap.axes

    attach_combo = ctx.attach_combo
    selected_axis = ctx.selected_axis
    fixed_applied = ctx.fixed_applied
    intents: list[Intent] = list(ctx.intents)

    fixed_axis = normalize_axis_id(inputs.fixed_axis)
    axis_id = normalize_axis_id(selected_axis or fixed_axis)
    attached = bool(selected_axis) or bool(fixed_axis)

    ui_axis_id = normalize_axis_id(getattr(ui, "axis_selected", ""))
    display_axis_id = axis_id or ui_axis_id
    if not display_axis_id and len(axis_ids) == 1:
        display_axis_id = axis_ids[0]

    # Compute param txn before presentation assembly so modal/txn state lands in the VM.
    presentation_phase_seed = compute_presentation_phase(
        engine=self,
        attach_combo=attach_combo,
        attached=bool(attached),
        axis_id=str(axis_id or ""),
        axis_ids=list(axis_ids),
        snap=snap,
        now_ns=int(inputs.now_ns),
        last_rx_ns=inputs.last_rx_ns,
        stale_after_ms=int(inputs.stale_after_ms),
        param_result=None,
        update_state=False,
    )

    param_result = run_param_txn(
        txn=self._param_txn,
        state=self.state,
        ui=ui,
        axis_id=str(axis_id or ""),
        now_ns=int(inputs.now_ns),
        estate=str(presentation_phase_seed.estate or ""),
        snap=presentation_phase_seed.snap_view,
        intents=intents,
        core_acks=list(inputs.core_acks or []),
    )

    presentation_phase = compute_presentation_phase(
        engine=self,
        attach_combo=attach_combo,
        attached=bool(attached),
        axis_id=str(axis_id or ""),
        axis_ids=list(axis_ids),
        snap=snap,
        now_ns=int(inputs.now_ns),
        last_rx_ns=inputs.last_rx_ns,
        stale_after_ms=int(inputs.stale_after_ms),
        param_result=param_result,
        update_state=True,
    )

    joy = getattr(snap, "joy", None) or JoyState()
    joy_state = project_local_joy(joy=joy, display_axis_id=str(display_axis_id or ""))

    motion_phase = compute_motion_phase(
        state=self.state,
        snap=snap,
        hip_id=hip_id,
        axis_id=str(axis_id or ""),
        axis_ids=list(axis_ids),
        display_axis_id=str(display_axis_id or ""),
        mode_now=str(presentation_phase.mode_now or ""),
        estop=bool(presentation_phase.estop),
        fault=bool(presentation_phase.fault),
        axes=axes,
        joy=joy_state,
        logical=dict(presentation_phase.logical),
        estate=str(presentation_phase.estate or ""),
        params=dict(presentation_phase.params or {}),
    )
    intents.extend(motion_phase.intents)

    self.state.joy_jog_active = bool(motion_phase.jog_allowed)
    self.state.joy_jog_axis = (
        str(motion_phase.motion_axis_id or "") if motion_phase.jog_allowed else ""
    )

    if ui.estop_reset_clicked and axis_id:
        intents.append(RequestEstopReset(axis_id=axis_id, hip_id=hip_id))

    if ui.main_reset_clicked and axis_id:
        intents.append(RequestMainReset(axis_id=axis_id, hip_id=hip_id))
    if ui.guider_reset_clicked and axis_id:
        intents.append(RequestGuiderReset(axis_id=axis_id, hip_id=hip_id))

    resync_ignored = False
    resync_reason = ""
    if ui.resync_clicked:
        estate_now = str(presentation_phase.estate or "").upper()
        if estate_now not in {"IDLE", "ARMED", "READY"}:
            resync_ignored = True
            resync_reason = (
                f"mode={str(presentation_phase.mode_now)} estate={str(presentation_phase.estate)}"
            )
        else:
            intents.append(RequestResync(axis_id=str(axis_id or ""), hip_id=hip_id))

    lifetick_intents, echo_map = self._compute_lifetick_echo_intents(
        snap=snap,
        hip_id=hip_id,
        last_lifetick_echo_sent=dict(self.state.last_lifetick_echo_sent or {}),
    )
    intents.extend(lifetick_intents)
    intents = gate_motion_intents(intents, deadman=self.state.joy.deadman)

    presentation = replace(
        presentation_phase.presentation,
        joy_deadman=bool(joy_state.joy_deadman),
        joy_select_hip=bool(joy_state.joy_select_hip),
        joy_soll_speed=float(joy_state.joy_soll_speed),
    )

    self.state.last_lifetick_echo_sent = dict(echo_map or {})
    self.state.selected_axis = str(selected_axis or "")
    self.state.fixed_axis_applied = bool(fixed_applied)
    self.state.prev_estop_profile = str(presentation_phase.profile or "")

    return HipStepResult(
        view_model=None,
        legacy_view_model=None,
        presentation=presentation,
        intents=intents,
        resync_ignored=bool(resync_ignored),
        resync_block_reason=str(resync_reason or ""),
        txn_events=list(param_result.txn_events or []),
    )
