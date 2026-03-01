from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from ..qtutil.param_ui_apply import apply_param_ui
from ..qtutil.ui_update import (
    set_enabled,
    set_enabled_repolish,
    set_state_by_object_name,
    set_state_property,
    update_slider
)
from ..qtutil.binder_helpers import block_signals, safe_set_text
from ..qtutil.ui_format import fmt_f_unit_de
from ..ui.joy_style import JOY_DEADMAN_PROP, JOY_SELECT_HIP_PROP

from ..panels.hip.hip_banner_render import apply_hip_banner
from ..panels.hip.hip_estop_render import apply_hip_estop
from ..panels.hip.hip_header_dots_render import apply_hip_header_dots
from ..panels.hip.hip_cut_markers_render import apply_hip_cut_markers
from ..panels.hip.hip_drive_status_render import apply_hip_drive_status
from ..panels.hip.hip_readouts_render import apply_hip_readouts
from ..panels.hip.hip_sliders_render import apply_hip_sliders

from ..engines.hip.attach_state import NOT_ATTACHED

if TYPE_CHECKING:
    from .hip_qt_binder import HipQtBinder
    from ..engines.hip.engine import HipViewModel

def apply(b, vm: HipViewModel) -> None:
    # Always-visible UI
    b.apply_tick_text(vm.tick_text)
    b._set_joy_properties(vm.joy_deadman, vm.joy_select_hip)
    b._apply_attach_state(vm)

    # Always keep axis picker in sync (if you moved it into _apply_attach_combo)
    b._apply_attach_combo(vm)

    b._apply_banner(vm)
    b._apply_header_dots(vm)
    b._apply_estop_state(vm)

    # Joy speed is display-only; safe to apply always
    b._apply_joy_speed(float(vm.joy_soll_speed))

    # Axis-dependent sections: only show/update when attached
    attached = bool(getattr(vm.attach_state, "attached", False)) if vm.attach_state is not None else False
    if not attached:
        # Optionally clear/hide axis-specific fields here (drive/readouts/params),
        # but do NOT return early before rendering global widgets.
        return

    b._apply_drive_status(vm)
    b._apply_readouts(vm)
    b._apply_sliders(vm)
    b._apply_cut_markers(vm)
    b._apply_params(vm)


def apply_startup_state(b) -> None:
    b.apply_tick_text("--")
    b._set_all_estop_unknown()
    b._set_joy_properties(False, False)
    b._apply_joy_speed(0.0)


def apply_tick_text(b, text: str) -> None:
    safe_set_text(b._txtTick, text)


def apply_online_state(b, state: str | None) -> None:
    if state is None:
        return
    b._set_dot("dotHdrOnline", state)


def _set_joy_properties(b, deadman: bool, select_hip: bool) -> None:
    # Joy UI reflection: QSS uses joy_deadman/joy_select_hip dynamic properties.
    if b._frame_footer is not None:
        set_state_property(
            b._frame_footer,
            bool(deadman),
            prop=JOY_DEADMAN_PROP,
        )
    if b._frame_header is not None:
        set_state_property(
            b._frame_header,
            bool(select_hip),
            prop=JOY_SELECT_HIP_PROP,
        )


def _apply_joy_speed(b, soll_speed: float) -> None:
    # sldVelCmd is display-only; updates are programmatic with signals blocked.
    if b._sld_vel_cmd is None:
        return
    try:
        v = float(soll_speed or 0.0)
    except Exception:
        v = 0.0
    if v < -1.0:
        v = -1.0
    elif v > 1.0:
        v = 1.0

    try:
        min_v = int(b._sld_vel_cmd.minimum())
        max_v = int(b._sld_vel_cmd.maximum())
    except Exception:
        min_v = 0
        max_v = 0

    if min_v >= 0 or max_v <= 0:
        scale = max(abs(min_v), abs(max_v), 1000)
        min_v = -scale
        max_v = scale
        update_slider(b._sld_vel_cmd, minimum=min_v, maximum=max_v)
    else:
        scale = max(abs(min_v), abs(max_v))
        if scale <= 0:
            scale = 1000

    value = int(round(v * scale))
    if value < min_v:
        value = min_v
    elif value > max_v:
        value = max_v
    update_slider(b._sld_vel_cmd, value=value)


# ------------------------------------------------------------------
# Apply helpers
# ------------------------------------------------------------------

def _apply_attach_combo(b, vm: HipViewModel) -> None:
    if vm.attach_combo is None or b._cmbAxis is None:
        return

    # Items come from the engine (Qt-free) and already include the NOT_ATTACHED sentinel.
    base_items = [str(x).strip() for x in (vm.attach_combo.items or []) if str(x).strip()]

    # Enforce the invariant: exactly one NOT_ATTACHED at the top.
    if not base_items:
        items = [NOT_ATTACHED]
    else:
        rest = [x for x in base_items if x != NOT_ATTACHED]
        items = [NOT_ATTACHED] + rest

    # VM's preferred selection is the source of truth, even while unattached.
    # This prevents a Qt Designer default combobox selection (e.g. "Anton") from
    # appearing selected on cold boot before the operator clicks.
    desired = (vm.attach_combo.current or "").strip() or NOT_ATTACHED
    if desired not in items:
        desired = NOT_ATTACHED

    existing = [b._cmbAxis.itemText(i) for i in range(b._cmbAxis.count())]
    need_rebuild = (existing != items) or (b._cmbAxis.currentText().strip() != desired)

    if need_rebuild:
        b._suppress_axis_signal = True
        try:
            with block_signals(b._cmbAxis):
                b._cmbAxis.clear()
                b._cmbAxis.addItems(items)
                b._cmbAxis.setCurrentText(desired)
        finally:
            b._suppress_axis_signal = False

    set_enabled(b._cmbAxis, bool(vm.attach_combo.enabled))


def _apply_attach_state(b, vm: HipViewModel) -> None:
    if vm.attach_state is None:
        return

    if b._tabs_main is not None and vm.attach_state.tabs_enabled is not None:
        set_enabled(b._tabs_main, bool(vm.attach_state.tabs_enabled))

    btn_setup = b._find_button("btnSetupToggle")
    btnMainReset = b._find_button("btnMainReset")
    btnGuiderReset = b._find_button("btnGuiderReset")
    btn_rec = b._find_button("btnRecover")
    if btn_setup is not None:
        set_enabled(btn_setup, bool(vm.attach_state.setup_enabled))
    if btnMainReset is not None:
        set_enabled(btnMainReset, bool(vm.attach_state.main_amp_reset_enabled))
    if btnGuiderReset is not None:
        set_enabled(btnGuiderReset, bool(getattr(vm.attach_state, "guider_amp_reset_enabled", False)))
    if btn_rec is not None:
        set_enabled(btn_rec, False)

    if b._btn_diag_resync is not None:
        set_enabled(b._btn_diag_resync, bool(vm.attach_state.resync_enabled))

    if b._btn_estop_reset is not None and vm.attach_state.estop_reset_enabled is not None:
        set_enabled(b._btn_estop_reset, bool(vm.attach_state.estop_reset_enabled))

    if not bool(vm.attach_state.attached):
        b._clear_for_unattached()


def _apply_drive_status(b, vm: HipViewModel) -> None:
    if b._drive_status_bindings is None:
        return
    apply_hip_drive_status(b._drive_status_bindings, vm)


def _apply_banner(b, vm: HipViewModel) -> None:
    if b._banner_bindings is None:
        return
    apply_hip_banner(b._banner_bindings, vm)


def _apply_header_dots(b, vm: HipViewModel) -> None:
    if b._header_dots_bindings is None:
        return
    apply_hip_header_dots(b._header_dots_bindings, vm)


def _apply_estop_state(b, vm: HipViewModel) -> None:
    if b._estop_bindings is None:
        return
    apply_hip_estop(b._estop_bindings, vm)


def _apply_readouts(b, vm: HipViewModel) -> None:
    if b._readouts_bindings is None:
        return
    ro = getattr(vm, "readouts", None)
    log = getattr(b, "log", None) or getattr(b, "_log", None)
    if log:
        log.info(
            "hi_p: dbg apply_readouts ro=%s bind=%s txtPos=%s",
            type(ro).__name__ if ro is not None else None,
            type(getattr(b, "_readouts_bindings", None)).__name__ if getattr(b, "_readouts_bindings", None) is not None else None,
            getattr(getattr(b, "_readouts_bindings", None), "txt_pos", None),
        )
    apply_hip_readouts(b._readouts_bindings, vm)


def _apply_sliders(b, vm: HipViewModel) -> None:
    if b._sliders_bindings is None:
        return
    apply_hip_sliders(b._sliders_bindings, vm)


def _apply_cut_markers(b, vm: HipViewModel) -> None:
    if b._cut_markers_bindings is None:
        return
    apply_hip_cut_markers(b._cut_markers_bindings, vm)


def _apply_params(b, vm: HipViewModel) -> None:
    if b._param_ui_bindings is None:
        return
    apply_param_ui(b._param_ui_bindings, vm)

# ------------------------------------------------------------------
# UI helpers
# ------------------------------------------------------------------
