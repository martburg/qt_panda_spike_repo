from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for type checking; avoids runtime import cycles.
    from .engine import HipEngine

from steuerung3d.core.intents import ClaimAxis, ReleaseAxis
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed

from .types import HipAttachCombo, HipStepInputs
from .attach_state import build_attach_combo


@dataclass(frozen=True)
class StepContext:
    snap: object
    ui: object
    hip_id: str
    axis_ids: list[str]
    attach_combo: HipAttachCombo
    selected_axis: str
    fixed_applied: bool
    intents: list[object]


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

    # Axis picker should present *live* DenSi devices only.
    # TelemetrySnapshot.densis is Core's discovery registry ("seen recently"),
    # whereas snap.axes may include configured axes even when no DenSi is running.
    densis = getattr(snap, "densis", None)
    densis = densis if isinstance(densis, dict) else {}
    axis_ids = sorted(
        [str(dev_id) for dev_id, d in densis.items() if bool(getattr(d, "online", False))]
    )

    ui_axis = str(ui.axis_selected or "").strip()
    if ui.axis_selection_changed:
        # Trust explicit user action.
        self.state.last_ui_axis_selected = ui_axis
    elif self.state.last_ui_axis_selected:
        # Sticky selection within a session (but not on cold boot).
        ui_axis = self.state.last_ui_axis_selected
    else:
        # Cold boot: start unattached. Some Qt UIs may have a default combobox
        # selection (e.g. "Anton") even before the operator touches it.
        # Exception: when the joystick explicitly requests selection (select_hip),
        # we treat the provided axis as intentional.
        if not (self.state.joy.select_hip and ui_axis and (ui_axis in axis_ids)):
            ui_axis = ""

    fixed_axis = str(inputs.fixed_axis or "").strip()
    prev_selected = str(self.state.selected_axis or "").strip()
    # If we were already attached to an axis that just went offline, keep it
    # visible in the picker so the operator can intentionally release it.
    if prev_selected and prev_selected not in axis_ids:
        axis_ids = list(axis_ids) + [prev_selected]
    # Normalize/dedupe while keeping deterministic ordering.
    axis_ids = sorted({str(x) for x in axis_ids if str(x).strip()})
    fixed_applied = bool(self.state.fixed_axis_applied)

    attach_combo, selected_axis, fixed_applied = build_attach_combo(
        axis_ids=list(axis_ids),
        ui_axis=str(ui_axis or ""),
        fixed_axis=str(fixed_axis or ""),
        prev_selected=str(prev_selected or ""),
        fixed_applied=bool(fixed_applied),
        lock_axis_combo=bool(inputs.lock_axis_combo),
    )

    intents: list[object] = []
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
