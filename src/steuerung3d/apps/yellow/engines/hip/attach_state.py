"""Attach/pool helpers for HipEngine (Qt-free)."""

from __future__ import annotations

from steuerung3d.core.axis_ids import normalize_axis_id

from .types import HipAttachCombo, HipAttachInputs, HipAttachState

NOT_ATTACHED = "NotAttached"


def compute_attach_state(inputs: HipAttachInputs) -> HipAttachState:
    attached = bool(inputs.attached)
    modal_locked = bool(inputs.modal_locked)
    last_estate = str(getattr(inputs, "last_estate", "") or "").upper()

    if attached and modal_locked:
        tabs_enabled: bool | None = None
    else:
        tabs_enabled = bool(attached) and (not modal_locked)

    setup_enabled = bool(attached) and (not modal_locked)
    main_amp_reset_enabled = bool(attached) and (not modal_locked)
    guider_amp_reset_enabled = bool(attached) and (not modal_locked)

    resync_enabled = bool(attached) and (not modal_locked) and (last_estate in {"IDLE", "ARMED", "READY"})

    estop_reset_enabled: bool | None = None if attached else False

    return HipAttachState(
        attached=attached,
        tabs_enabled=tabs_enabled,
        setup_enabled=setup_enabled,
        main_amp_reset_enabled=main_amp_reset_enabled,
        guider_amp_reset_enabled=guider_amp_reset_enabled,
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
    # Normalize only for comparisons; keep canonical axis ids from `axis_ids`
    # for downstream dict keys.
    axis_norm_to_canon = {normalize_axis_id(a): a for a in (axis_ids or []) if a}
    ui_axis_norm = normalize_axis_id(ui_axis)
    fixed_axis_norm = normalize_axis_id(fixed_axis)
    prev_selected_norm = normalize_axis_id(prev_selected)

    items = [NOT_ATTACHED] + list(axis_ids)
    combo_enabled = True
    combo_current = NOT_ATTACHED

    if fixed_axis_norm and fixed_axis_norm in axis_norm_to_canon:
        selected_axis = axis_norm_to_canon[fixed_axis_norm]
        combo_current = selected_axis
        fixed_applied = True
        combo_enabled = not (bool(lock_axis_combo) and fixed_applied)
    else:
        if ui_axis_norm and ui_axis_norm in axis_norm_to_canon:
            selected_axis = axis_norm_to_canon[ui_axis_norm]
        elif ui_axis == NOT_ATTACHED or not ui_axis:
            selected_axis = ""
        else:
            selected_axis = ""

        if ui_axis in items:
            combo_current = ui_axis
        elif prev_selected_norm and prev_selected_norm in axis_norm_to_canon:
            combo_current = axis_norm_to_canon[prev_selected_norm]
        else:
            combo_current = NOT_ATTACHED

    attach_combo = HipAttachCombo(
        items=items,
        current=combo_current,
        enabled=bool(combo_enabled),
        fixed_axis_applied=bool(fixed_applied),
    )
    return attach_combo, str(selected_axis or ""), bool(fixed_applied)
