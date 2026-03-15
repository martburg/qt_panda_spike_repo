"""HiP engine step pipeline (extracted).

No semantic changes intended; this is a mechanical extraction from `engine.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Mapping, Sequence

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
from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot

from .intent_policy import gate_motion_intents
from .param_ui import ParamTxnResult, run_param_txn
from .step_context import build_step_context
from .step_phase_motion import HipJoyProjectionState, compute_motion_phase, project_local_joy
from .step_phase_presentation import HipPresentationPhase, compute_presentation_phase
from .types import HipAttachCombo, HipPresentationData, HipStepInputs, HipStepResult, HipUiInputs


@dataclass(frozen=True)
class _StepState:
    snap: TelemetrySnapshot
    ui: HipUiInputs
    hip_id: str
    axis_ids: Sequence[str]
    axes: Mapping[str, AxisTelemetry]
    attach_combo: HipAttachCombo
    selected_axis: str
    fixed_applied: bool
    intents: list[Intent]
    fixed_axis: str
    axis_id: str
    attached: bool
    display_axis_id: str


@dataclass(frozen=True)
class _PreMotionResult:
    param_result: ParamTxnResult
    presentation_phase: HipPresentationPhase
    joy_state: HipJoyProjectionState


@dataclass(frozen=True)
class _CommandPhaseResult:
    intents: list[Intent]
    resync_ignored: bool
    resync_reason: str
    presentation: HipPresentationData
    echo_map: dict[str, int]


def _build_step_state(*, engine: "HipEngine", inputs: HipStepInputs) -> _StepState:
    ctx = build_step_context(engine=engine, inputs=inputs)
    snap = ctx.snap
    ui = ctx.ui
    axis_ids = ctx.axis_ids
    fixed_axis = normalize_axis_id(inputs.fixed_axis)
    axis_id = normalize_axis_id(ctx.selected_axis or fixed_axis)
    attached = bool(ctx.selected_axis) or bool(fixed_axis)
    ui_axis_id = normalize_axis_id(getattr(ui, "axis_selected", ""))
    display_axis_id = axis_id or ui_axis_id
    if not display_axis_id and len(axis_ids) == 1:
        display_axis_id = axis_ids[0]
    return _StepState(
        snap=snap,
        ui=ui,
        hip_id=ctx.hip_id,
        axis_ids=axis_ids,
        axes=snap.axes,
        attach_combo=ctx.attach_combo,
        selected_axis=ctx.selected_axis,
        fixed_applied=ctx.fixed_applied,
        intents=list(ctx.intents),
        fixed_axis=fixed_axis,
        axis_id=axis_id,
        attached=attached,
        display_axis_id=display_axis_id,
    )


def _run_pre_motion_phases(
    *, engine: "HipEngine", inputs: HipStepInputs, step_state: _StepState
) -> _PreMotionResult:
    presentation_phase_seed = compute_presentation_phase(
        engine=engine,
        attach_combo=step_state.attach_combo,
        attached=bool(step_state.attached),
        axis_id=str(step_state.axis_id or ""),
        axis_ids=step_state.axis_ids,
        snap=step_state.snap,
        now_ns=int(inputs.now_ns),
        last_rx_ns=inputs.last_rx_ns,
        stale_after_ms=int(inputs.stale_after_ms),
        param_result=None,
        update_state=False,
    )
    param_result = run_param_txn(
        txn=engine._param_txn,
        state=engine.state,
        ui=step_state.ui,
        axis_id=str(step_state.axis_id or ""),
        now_ns=int(inputs.now_ns),
        estate=str(presentation_phase_seed.estate or ""),
        snap=presentation_phase_seed.snap_view,
        intents=step_state.intents,
        core_acks=list(inputs.core_acks or []),
    )
    presentation_phase = compute_presentation_phase(
        engine=engine,
        attach_combo=step_state.attach_combo,
        attached=bool(step_state.attached),
        axis_id=str(step_state.axis_id or ""),
        axis_ids=step_state.axis_ids,
        snap=step_state.snap,
        now_ns=int(inputs.now_ns),
        last_rx_ns=inputs.last_rx_ns,
        stale_after_ms=int(inputs.stale_after_ms),
        param_result=param_result,
        update_state=True,
    )
    joy_state = project_local_joy(
        joy=inputs.joy,
        display_axis_id=str(step_state.display_axis_id or ""),
    )
    return _PreMotionResult(
        param_result=param_result,
        presentation_phase=presentation_phase,
        joy_state=joy_state,
    )


def _append_reset_and_resync_intents(
    *,
    axis_id: str,
    hip_id: str,
    presentation_phase: HipPresentationPhase,
    ui: HipUiInputs,
    intents: list[Intent],
) -> tuple[bool, str]:
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
    return resync_ignored, resync_reason


def _run_motion_and_command_phases(
    *,
    engine: "HipEngine",
    step_state: _StepState,
    pre_motion: _PreMotionResult,
) -> _CommandPhaseResult:
    intents = list(step_state.intents)
    motion_phase = compute_motion_phase(
        state=engine.state,
        snap=step_state.snap,
        hip_id=step_state.hip_id,
        axis_id=str(step_state.axis_id or ""),
        axis_ids=step_state.axis_ids,
        display_axis_id=str(step_state.display_axis_id or ""),
        mode_now=str(pre_motion.presentation_phase.mode_now or ""),
        estop=bool(pre_motion.presentation_phase.estop),
        fault=bool(pre_motion.presentation_phase.fault),
        axes=step_state.axes,
        joy=pre_motion.joy_state,
        logical=dict(pre_motion.presentation_phase.logical),
        estate=str(pre_motion.presentation_phase.estate or ""),
        params=dict(pre_motion.presentation_phase.params or {}),
    )
    intents.extend(motion_phase.intents)
    engine.state.joy_jog_active = bool(motion_phase.jog_allowed)
    engine.state.joy_jog_axis = (
        str(motion_phase.motion_axis_id or "") if motion_phase.jog_allowed else ""
    )

    resync_ignored, resync_reason = _append_reset_and_resync_intents(
        axis_id=step_state.axis_id,
        hip_id=step_state.hip_id,
        presentation_phase=pre_motion.presentation_phase,
        ui=step_state.ui,
        intents=intents,
    )
    lifetick_intents, echo_map = engine._compute_lifetick_echo_intents(
        snap=step_state.snap,
        hip_id=step_state.hip_id,
        selected_axis=step_state.axis_id,
        last_lifetick_echo_sent=dict(engine.state.last_lifetick_echo_sent or {}),
    )
    intents.extend(lifetick_intents)
    intents = gate_motion_intents(intents, deadman=engine.state.joy.deadman)
    presentation = replace(
        pre_motion.presentation_phase.presentation,
        joy_deadman=bool(pre_motion.joy_state.joy_deadman),
        joy_select_hip=bool(pre_motion.joy_state.joy_select_hip),
        joy_soll_speed=float(pre_motion.joy_state.joy_soll_speed),
    )
    return _CommandPhaseResult(
        intents=intents,
        resync_ignored=bool(resync_ignored),
        resync_reason=str(resync_reason or ""),
        presentation=presentation,
        echo_map=dict(echo_map or {}),
    )


def _apply_post_step_state(
    *,
    engine: "HipEngine",
    step_state: _StepState,
    pre_motion: _PreMotionResult,
    command_phase: _CommandPhaseResult,
) -> None:
    engine.state.last_lifetick_echo_sent = dict(command_phase.echo_map or {})
    engine.state.selected_axis = str(step_state.selected_axis or "")
    engine.state.fixed_axis_applied = bool(step_state.fixed_applied)
    engine.state.prev_estop_profile = str(pre_motion.presentation_phase.profile or "")


def _build_step_result(
    *, command_phase: _CommandPhaseResult, param_result: ParamTxnResult
) -> HipStepResult:
    return HipStepResult(
        view_model=None,
        legacy_view_model=None,
        presentation=command_phase.presentation,
        intents=command_phase.intents,
        resync_ignored=bool(command_phase.resync_ignored),
        resync_block_reason=str(command_phase.resync_reason or ""),
        txn_events=list(param_result.txn_events or []),
    )


def step(*, engine: "HipEngine", inputs: HipStepInputs) -> HipStepResult:
    """Run one HiP engine tick."""
    step_state = _build_step_state(engine=engine, inputs=inputs)
    pre_motion = _run_pre_motion_phases(engine=engine, inputs=inputs, step_state=step_state)
    command_phase = _run_motion_and_command_phases(
        engine=engine,
        step_state=step_state,
        pre_motion=pre_motion,
    )
    _apply_post_step_state(
        engine=engine,
        step_state=step_state,
        pre_motion=pre_motion,
        command_phase=command_phase,
    )
    return _build_step_result(command_phase=command_phase, param_result=pre_motion.param_result)
