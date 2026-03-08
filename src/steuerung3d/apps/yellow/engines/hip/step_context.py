from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    # Only needed for type checking; avoids runtime import cycles.
    from .engine import HipEngine

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.intents import ClaimAxis, Intent, ReleaseAxis
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed
from steuerung3d.core.telemetry import DensiTelemetry, TelemetrySnapshot

from .attach_state import NOT_ATTACHED, build_attach_combo
from .types import HipAttachCombo, HipStepInputs, HipUiInputs


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


def _claim_owner_by_axis(*, densis: Mapping[str, DensiTelemetry], axis_id: str) -> str:
    d = densis.get(str(axis_id or ""))
    if d is None:
        return ""
    return str(getattr(d, "claimed_by_hip", "") or "")


def _visible_axis_ids_for_hip(
    *, densis: Mapping[str, DensiTelemetry], hip_id: str, prev_selected: str
) -> list[str]:
    visible: list[str] = []
    hip_id = str(hip_id or "")
    prev_selected = str(prev_selected or "")

    for dev_id, d in densis.items():
        axis_id = str(dev_id or "").strip()
        if not axis_id:
            continue

        owner = str(getattr(d, "claimed_by_hip", "") or "")
        online = bool(getattr(d, "online", False))

        if online and owner in ("", hip_id):
            visible.append(axis_id)
            continue

        if axis_id == prev_selected and owner == hip_id:
            visible.append(axis_id)

    return sorted({x for x in visible if x.strip()})


def _authoritative_selected_axis(
    *, densis: Mapping[str, DensiTelemetry], hip_id: str, selected_axis: str, prev_selected: str
) -> str:
    hip_id = str(hip_id or "")
    selected_axis = str(selected_axis or "")
    prev_selected = str(prev_selected or "")

    if selected_axis:
        owner = _claim_owner_by_axis(densis=densis, axis_id=selected_axis)
        if owner == hip_id:
            return selected_axis

    if prev_selected:
        owner = _claim_owner_by_axis(densis=densis, axis_id=prev_selected)
        if owner == hip_id:
            return prev_selected

    return ""


def _densis_dbg(densis: Mapping[str, DensiTelemetry]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for k, d in densis.items():
        out[str(k)] = {
            "online": bool(getattr(d, "online", False)),
            "owner": str(getattr(d, "claimed_by_hip", "") or ""),
        }
    return out


def build_step_context(*, engine: "HipEngine", inputs: HipStepInputs) -> StepContext:
    """Normalize HiP step inputs into a small, testable context object."""
    self = engine

    snap = inputs.snap
    ui = inputs.ui
    hip_id = str(inputs.hip_id or "")

    joy_in = inputs.joy if isinstance(inputs.joy, JoyState) else JoyState()
    self.state.joy = JoyState(
        deadman=bool(getattr(joy_in, "deadman", False)),
        select_hip=bool(getattr(joy_in, "select_hip", False)),
        soll_speed=clamp_soll_speed(getattr(joy_in, "soll_speed", 0.0)),
    )
    if getattr(self._param_txn, "hip_id", "") != hip_id:
        self._param_txn.hip_id = hip_id

    densis = snap.densis

    prev_selected = str(self.state.selected_axis or "")
    axis_ids = _visible_axis_ids_for_hip(
        densis=densis,
        hip_id=hip_id,
        prev_selected=prev_selected,
    )
    axis_norm_to_canon = {normalize_axis_id(a): a for a in (axis_ids or []) if a}

    ui_axis = str(ui.axis_selected or "").strip()
    ui_axis_norm = normalize_axis_id(ui_axis)
    if ui.axis_selection_changed:
        self.state.last_ui_axis_selected = ui_axis
    elif self.state.last_ui_axis_selected:
        ui_axis = self.state.last_ui_axis_selected
        ui_axis_norm = normalize_axis_id(ui_axis)
    else:
        if not (
            self.state.joy.select_hip and ui_axis_norm and (ui_axis_norm in axis_norm_to_canon)
        ):
            ui_axis = ""
            ui_axis_norm = ""

    fixed_axis = normalize_axis_id(inputs.fixed_axis)
    fixed_applied = bool(self.state.fixed_axis_applied)

    attach_combo, selected_axis, fixed_applied = build_attach_combo(
        axis_ids=list(axis_ids),
        ui_axis=str(ui_axis or ""),
        fixed_axis=str(fixed_axis or ""),
        prev_selected=str(prev_selected or ""),
        fixed_applied=bool(fixed_applied),
        lock_axis_combo=bool(inputs.lock_axis_combo),
    )

    authoritative_axis = _authoritative_selected_axis(
        densis=densis,
        hip_id=hip_id,
        selected_axis=selected_axis,
        prev_selected=prev_selected,
    )

    if ui.axis_selection_changed:
        requested = str(ui.axis_selected or "").strip()
        illegal_foreign_request = bool(
            requested and requested != NOT_ATTACHED and requested not in axis_ids
        )
        if illegal_foreign_request:
            selected_axis = authoritative_axis
            attach_combo = HipAttachCombo(
                items=list(attach_combo.items),
                current=str(selected_axis or NOT_ATTACHED),
                enabled=bool(attach_combo.enabled),
                fixed_axis_applied=bool(attach_combo.fixed_axis_applied),
            )
    else:
        selected_axis = authoritative_axis
        attach_combo = HipAttachCombo(
            items=list(attach_combo.items),
            current=str(selected_axis or NOT_ATTACHED),
            enabled=bool(attach_combo.enabled),
            fixed_axis_applied=bool(attach_combo.fixed_axis_applied),
        )

    intents: list[Intent] = []
    if ui.axis_selection_changed:
        if prev_selected and (not selected_axis or prev_selected != selected_axis):
            intents.append(ReleaseAxis(axis_id=prev_selected, hip_id=hip_id))
        if selected_axis and selected_axis != prev_selected:
            intents.append(ClaimAxis(axis_id=selected_axis, hip_id=hip_id))

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
