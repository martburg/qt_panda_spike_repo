"""Attach/pool helpers for HipEngine (Qt-free)."""

from __future__ import annotations

from .types import HipAttachCombo, HipAttachInputs, HipAttachState

NOT_ATTACHED = "NotAttached"


def compute_attach_state(inputs: HipAttachInputs) -> HipAttachState:
    attached = bool(inputs.attached)
    modal_locked = bool(inputs.modal_locked)
    last_mode = str(inputs.last_mode or "").upper()
    last_estate = str(inputs.last_estate or "").upper()

    if attached and modal_locked:
        tabs_enabled: bool | None = None
    else:
        tabs_enabled = bool(attached) and (not modal_locked)

    setup_enabled = bool(attached) and (not modal_locked)
    main_amp_reset_enabled = bool(attached) and (not modal_locked)

    resync_enabled = (
        bool(attached)
        and (not modal_locked)
        and (last_mode == "IDLE")
        and (last_estate == "IDLE")
    )

    estop_reset_enabled: bool | None = None if attached else False

    return HipAttachState(
        attached=attached,
        tabs_enabled=tabs_enabled,
        setup_enabled=setup_enabled,
        main_amp_reset_enabled=main_amp_reset_enabled,
        resync_enabled=resync_enabled,
        estop_reset_enabled=estop_reset_enabled,
    )


def build_attach_combo(
    *,
    axis_ids: list[str],
    ui_axis: str,
    fixed_axis: str,
    prev_selected: str,
    fixed_applied: bool,
    lock_axis_combo: bool,
) -> tuple[HipAttachCombo, str, bool]:
    items = [NOT_ATTACHED] + list(axis_ids)
    combo_enabled = True
    combo_current = NOT_ATTACHED

    if fixed_axis and fixed_axis in axis_ids:
        selected_axis = fixed_axis
        combo_current = fixed_axis
        fixed_applied = True
        combo_enabled = not (bool(lock_axis_combo) and fixed_applied)
    else:
        if ui_axis in axis_ids:
            selected_axis = ui_axis
        elif ui_axis == NOT_ATTACHED or not ui_axis:
            selected_axis = ""
        else:
            selected_axis = ""

        if ui_axis in items:
            combo_current = ui_axis
        elif prev_selected in axis_ids:
            combo_current = prev_selected
        else:
            combo_current = NOT_ATTACHED

    attach_combo = HipAttachCombo(
        items=items,
        current=combo_current,
        enabled=bool(combo_enabled),
        fixed_axis_applied=bool(fixed_applied),
    )
    return attach_combo, str(selected_axis or ""), bool(fixed_applied)
