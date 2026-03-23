from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.axis_selection import authoritative_selected_axis, visible_axis_ids_for_hip
from steuerung3d.core.intents import ClaimAxis, Intent, ReleaseAxis
from steuerung3d.core.joy_state import JoyState, clamp_norm, clamp_soll_speed
from steuerung3d.core.telemetry import TelemetrySnapshot

from .attach_state import NOT_ATTACHED, build_attach_combo
from .types import HipAttachCombo, HipStepContextEngineLike, HipStepInputs, HipUiInputs


@dataclass(frozen=True)
class StepContext:
    snap: TelemetrySnapshot
    ui: HipUiInputs
    hip_id: str
    axis_ids: list[str]
    attach_combo: HipAttachCombo
    selected_axis: str
    fixed_applied: bool
    intents: list[Intent]


def _sync_joy_state(runtime: HipStepContextEngineLike, hip_id: str, joy: JoyState | object) -> None:
    joy_in = joy if isinstance(joy, JoyState) else JoyState()
    runtime.state.joy = JoyState(
        deadman=bool(getattr(joy_in, "deadman", False)),
        select_hip=bool(getattr(joy_in, "select_hip", False)),
        soll_speed=clamp_soll_speed(getattr(joy_in, "soll_speed", 0.0)),
        look_pan=clamp_norm(getattr(joy_in, "look_pan", 0.0)),
        look_tilt=clamp_norm(getattr(joy_in, "look_tilt", 0.0)),
        selected_axes=getattr(joy_in, "selected_axes", ()),
    )
    if getattr(runtime._param_txn, "hip_id", "") != hip_id:
        runtime._param_txn.hip_id = hip_id


def _visible_axis_context(
    *, snap: TelemetrySnapshot, hip_id: str, prev_selected: str, fixed_axis: str
) -> tuple[list[str], dict[str, str]]:
    axis_ids = visible_axis_ids_for_hip(
        densis=snap.densis, hip_id=hip_id, prev_selected=prev_selected
    )
    fixed_norm = normalize_axis_id(fixed_axis)
    if fixed_norm:
        # For supervisor-opened HiPs, always surface the fixed axis if it exists
        # in the current snapshot, even before claim ownership is established.
        axis_norm_to_canon_all = {
            normalize_axis_id(str(a)): str(a)
            for a in list((getattr(snap, "axes", {}) or {}).keys())
            + list((getattr(snap, "densis", {}) or {}).keys())
            if str(a).strip()
        }
        canon = axis_norm_to_canon_all.get(fixed_norm)
        if canon and canon not in axis_ids:
            axis_ids.append(canon)
    axis_ids = sorted({str(a) for a in (axis_ids or []) if str(a).strip()})
    axis_norm_to_canon = {normalize_axis_id(a): a for a in (axis_ids or []) if a}
    return list(axis_ids), axis_norm_to_canon


def _resolve_ui_axis(
    *, runtime: HipStepContextEngineLike, ui: HipUiInputs, axis_norm_to_canon: dict[str, str]
) -> str:
    ui_axis = str(ui.axis_selected or "").strip()
    ui_axis_norm = normalize_axis_id(ui_axis)
    if ui.axis_selection_changed:
        runtime.state.last_ui_axis_selected = ui_axis
        return ui_axis
    if runtime.state.last_ui_axis_selected:
        return str(runtime.state.last_ui_axis_selected)
    if not (runtime.state.joy.select_hip and ui_axis_norm and (ui_axis_norm in axis_norm_to_canon)):
        return ""
    return ui_axis


def _build_attach_context(
    *,
    runtime: HipStepContextEngineLike,
    inputs: HipStepInputs,
    axis_ids: list[str],
    ui_axis: str,
    prev_selected: str,
) -> tuple[HipAttachCombo, str, bool]:
    fixed_axis = normalize_axis_id(inputs.fixed_axis)
    return build_attach_combo(
        axis_ids=list(axis_ids),
        ui_axis=str(ui_axis or ""),
        fixed_axis=str(fixed_axis or ""),
        prev_selected=str(prev_selected or ""),
        fixed_applied=bool(runtime.state.fixed_axis_applied),
        lock_axis_combo=bool(inputs.lock_axis_combo),
    )


def _apply_authoritative_selection(
    *,
    snap: TelemetrySnapshot,
    hip_id: str,
    ui: HipUiInputs,
    axis_ids: list[str],
    prev_selected: str,
    attach_combo: HipAttachCombo,
    selected_axis: str,
    fixed_axis: str,
) -> tuple[HipAttachCombo, str]:
    authoritative_axis = authoritative_selected_axis(
        densis=snap.densis,
        hip_id=hip_id,
        selected_axis=selected_axis,
        prev_selected=prev_selected,
    )
    fixed_norm = normalize_axis_id(fixed_axis)
    selected_norm = normalize_axis_id(selected_axis)
    preserve_fixed_selection = bool(fixed_norm and selected_norm and fixed_norm == selected_norm)
    if ui.axis_selection_changed:
        requested = str(ui.axis_selected or "").strip()
        illegal_foreign_request = bool(
            requested and requested != NOT_ATTACHED and requested not in axis_ids
        )
        if illegal_foreign_request:
            selected_axis = selected_axis if preserve_fixed_selection else authoritative_axis
    else:
        selected_axis = selected_axis if preserve_fixed_selection else authoritative_axis
    attach_combo = HipAttachCombo(
        items=list(attach_combo.items),
        current=str(selected_axis or NOT_ATTACHED),
        enabled=bool(attach_combo.enabled),
        fixed_axis_applied=bool(attach_combo.fixed_axis_applied),
    )
    return attach_combo, str(selected_axis or "")


def _build_selection_intents(
    *, ui: HipUiInputs, prev_selected: str, selected_axis: str, hip_id: str, fixed_axis: str
) -> list[Intent]:
    intents: list[Intent] = []
    fixed_norm = normalize_axis_id(fixed_axis)
    auto_claim_fixed = bool(fixed_norm and normalize_axis_id(selected_axis) == fixed_norm)
    if not ui.axis_selection_changed and not auto_claim_fixed:
        return intents
    if prev_selected and (not selected_axis or prev_selected != selected_axis):
        intents.append(ReleaseAxis(axis_id=prev_selected, hip_id=hip_id))
    if selected_axis and selected_axis != prev_selected:
        intents.append(ClaimAxis(axis_id=selected_axis, hip_id=hip_id))
    return intents


def build_step_context(*, runtime: HipStepContextEngineLike, inputs: HipStepInputs) -> StepContext:
    """Normalize HiP step inputs into a small, testable context object."""
    snap = inputs.snap
    ui = inputs.ui
    hip_id = str(inputs.hip_id or "")

    _sync_joy_state(runtime, hip_id, inputs.joy)
    prev_selected = str(runtime.state.selected_axis or "")
    axis_ids, axis_norm_to_canon = _visible_axis_context(
        snap=snap,
        hip_id=hip_id,
        prev_selected=prev_selected,
        fixed_axis=inputs.fixed_axis,
    )
    ui_axis = _resolve_ui_axis(runtime=runtime, ui=ui, axis_norm_to_canon=axis_norm_to_canon)
    attach_combo, selected_axis, fixed_applied = _build_attach_context(
        runtime=runtime,
        inputs=inputs,
        axis_ids=axis_ids,
        ui_axis=ui_axis,
        prev_selected=prev_selected,
    )
    attach_combo, selected_axis = _apply_authoritative_selection(
        snap=snap,
        hip_id=hip_id,
        ui=ui,
        axis_ids=axis_ids,
        prev_selected=prev_selected,
        attach_combo=attach_combo,
        selected_axis=selected_axis,
        fixed_axis=inputs.fixed_axis,
    )
    intents = _build_selection_intents(
        ui=ui,
        prev_selected=prev_selected,
        selected_axis=selected_axis,
        hip_id=hip_id,
        fixed_axis=inputs.fixed_axis,
    )
    return StepContext(
        snap=snap,
        ui=ui,
        hip_id=hip_id,
        axis_ids=list(axis_ids),
        attach_combo=attach_combo,
        selected_axis=str(selected_axis or ""),
        fixed_applied=bool(fixed_applied),
        intents=intents,
    )
