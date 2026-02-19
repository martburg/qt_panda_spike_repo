"""Qt-only binder for HiP.

Responsibilities:
- Discover widgets.
- Wire signals to capture UI actions.
- Read UI inputs into HipUiInputs.
- Apply HipViewModel to widgets.

Business rules and intent policy live in the engine/controller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from PySide6.QtWidgets import (
    QAbstractSlider,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QWidget,
)

from ..qtutil.ui_panel_state import clear_line_edits, neutralize_dots, uncheck_checkboxes
from ..qtutil.param_widget_binder import ParamWidgetBinder
from ..qtutil.ui_update import (
    set_checked,
    set_enabled,
    set_enabled_repolish,
    set_state_by_object_name,
    set_state_property,
    set_text,
    update_slider,
)
from ..qtutil.widget_cache import WidgetCache
from ..qtutil.ui_contract import log_missing_optional_once, log_missing_required_once
from ..domain.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS, LIMIT_WIDGETS as _LIMIT_WIDGETS
from ..domain.ui_format import fmt_f_unit
from ..domain.ui_banner import BANNER_COLORS
from ..engines.hip.engine import (
    HipParamAction,
    HipUiInputs,
    HipViewModel,
)
from steuerung3d.protocol.estop_bits import ESTOP_SPECS


@dataclass
class HipQtBinder:
    win: QWidget
    log: logging.Logger

    _events: list[HipParamAction] = field(default_factory=list)
    _estop_reset_clicked: bool = False
    _resync_clicked: bool = False
    _axis_selection_changed: bool = False
    _axis_selected_value: str = ""
    _suppress_axis_signal: bool = False

    def __post_init__(self) -> None:
        self._wcache = WidgetCache(self.win)
        self._param_binder = ParamWidgetBinder(
            self.win,
            self.log,
            _PARAM_WIDGETS,
            _LIMIT_WIDGETS,
            cache=self._wcache,
        )

        # Core widgets
        self._tabs_main: QTabWidget | None = self._wcache.get(QTabWidget, "tabsMain")
        self._cmbAxis: QComboBox | None = self.win.findChild(QComboBox, "cmbAxis")

        # Header + tick
        self._txtTick: QLineEdit | None = self.win.findChild(QLineEdit, "txtTick")
        self._txt_hdr_banner_left: QLineEdit | None = self.win.findChild(QLineEdit, "txtHdrBannerLeft")
        self._txt_hdr_banner_right: QLineEdit | None = self.win.findChild(
            QLineEdit, "txtHdrBannerRight"
        )
        self._frame_header: QWidget | None = self.win.findChild(QWidget, "frameHeader")
        self._frame_footer: QWidget | None = self.win.findChild(QWidget, "frameFooter")

        # Drive status fields
        self._txt_main_amp_status: QLineEdit | None = self.win.findChild(QLineEdit, "txtMainAmpStatus")
        self._txt_slave_amp_status: QLineEdit | None = self.win.findChild(QLineEdit, "txtSlaveAmpStatus")

        # Readouts
        self._txtPos: QLineEdit | None = self.win.findChild(QLineEdit, "txtPos")
        self._txtVel: QLineEdit | None = self.win.findChild(QLineEdit, "txtVel")
        self._txtAmp: QLineEdit | None = self.win.findChild(QLineEdit, "txtAmp")
        self._txtTemp: QLineEdit | None = self.win.findChild(QLineEdit, "txtTemp")

        self._txtCutPos: QLineEdit | None = self.win.findChild(QLineEdit, "txtCutPos")
        self._txtCutVel: QLineEdit | None = self.win.findChild(QLineEdit, "txtCutVel")
        self._txtCutTime: QLineEdit | None = self.win.findChild(QLineEdit, "txtCutTime")
        self._txtPosdiff: QLineEdit | None = self.win.findChild(QLineEdit, "txtPosdiff")

        self._txt_guider_range_min: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeMin")
        self._txt_guider_range_max: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeMax")
        self._txt_guider_range_val: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeValue")
        self._txt_guider_speed: QLineEdit | None = self.win.findChild(
            QLineEdit, "txtGuiderSpeed"
        )

        # Sliders
        self._sld_vel_cmd: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldVelCmd")
        self._sld_limit_range: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldLimitRange")
        self._sld_guider_range: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldGuiderRange")
        self._sld_guider_speed: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldGuiderSpeed")

        # Buttons
        self._btn_estop_reset: QPushButton | None = self.win.findChild(
            QPushButton, "btnEStopReset"
        )
        self._btn_diag_resync: QPushButton | None = self.win.findChild(
            QPushButton, "btnDiagResync"
        )

        if self._txt_hdr_banner_right is None:
            raise RuntimeError("UI is missing widget named 'txtHdrBannerRight'")
        if self._txt_guider_speed is None:
            raise RuntimeError("UI is missing widget named 'txtGuiderSpeed'")
        if self._btn_estop_reset is None:
            raise RuntimeError("UI is missing widget named 'btnEStopReset'")
        if self._btn_diag_resync is None:
            raise RuntimeError("UI is missing widget named 'btnDiagResync'")

        # Estop diagnostic checkboxes (read-only)
        self._estop_checks: dict[str, QCheckBox] = {}
        for spec in ESTOP_SPECS.values():
            if not spec.checkbox:
                continue
            cb = self.win.findChild(QCheckBox, spec.checkbox)
            if cb is not None:
                cb.setEnabled(False)
                self._estop_checks[spec.key] = cb

        if self._btn_estop_reset is not None:
            set_enabled(self._btn_estop_reset, False)
        if self._btn_diag_resync is not None:
            set_enabled(self._btn_diag_resync, False)

        # Modal lock helpers
        try:
            self._modal_widgets = [
                w
                for w in self.win.findChildren(QWidget)
                if isinstance(w, (QPushButton, QLineEdit))
            ]
        except Exception:
            self._modal_widgets = []
        self._modal_locked = False
        self._modal_prev_enabled: dict[QWidget, bool] = {}
        self._modal_prev_tabbar_enabled: bool | None = None

        # Param input validators (numeric)
        self._init_param_inputs()

        # UI contract checks
        log_missing_required_once(
            self.log,
            self._wcache,
            [
                (QComboBox, "cmbAxis"),
                (QLineEdit, "txtTick"),
                (QLineEdit, "txtHdrBannerLeft"),
                (QLineEdit, "txtHdrBannerRight"),
            ],
            context="hi_p:required",
        )
        log_missing_optional_once(
            self.log,
            self._wcache,
            [
                (QWidget, "dotHdrOnline"),
                (QWidget, "dotHdrReady"),
                (QWidget, "dotHdrFbt"),
                (QWidget, "dotHdrBrake1"),
                (QWidget, "dotHdrBrake2"),
            ],
            context="hi_p:hdr_dots",
        )
        log_missing_optional_once(
            self.log,
            self._wcache,
            [
                (QLineEdit, "txtTick"),
                (QLineEdit, "txtPos"),
                (QLineEdit, "txtVel"),
                (QLineEdit, "txtAmp"),
                (QLineEdit, "txtTemp"),
            ],
            context="hi_p:readouts",
        )

        self._wire_signals()

    # ------------------------------------------------------------------
    # Signal wiring / input capture
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        if self._cmbAxis is not None:
            self._cmbAxis.currentTextChanged.connect(self._on_axis_selected)
        if self._btn_estop_reset is not None:
            self._btn_estop_reset.clicked.connect(self._on_estop_reset_clicked)
        if self._btn_diag_resync is not None:
            self._btn_diag_resync.clicked.connect(self._on_resync_clicked)

        wiring = {
            "pos": ("btnPosEdit", "btnPosWrite", "btnPosCancel"),
            "vel": ("btnVelEdit", "btnVelWrite", "btnVelCancel"),
            "filter": ("btnFilterEdit", "btnFilterWrite", "btnFilterCancel"),
            "guider": ("btnGuiderEdit", "btnGuiderWrite", "btnGuiderCancel"),
        }
        for grp, (b_edit, b_write, b_cancel) in wiring.items():
            be = self._find_button(b_edit)
            bw = self._find_button(b_write)
            bc = self._find_button(b_cancel)
            if be is not None:
                be.clicked.connect(lambda _=False, g=grp: self._on_param_action("edit", g))
            if bw is not None:
                bw.clicked.connect(lambda _=False, g=grp: self._on_param_action("write", g))
            if bc is not None:
                bc.clicked.connect(lambda _=False, g=grp: self._on_param_action("cancel", g))

    def _on_estop_reset_clicked(self) -> None:
        self._estop_reset_clicked = True

    def _on_resync_clicked(self) -> None:
        self._resync_clicked = True

    def _on_axis_selected(self, axis_id: str) -> None:
        if self._suppress_axis_signal:
            return
        self._axis_selection_changed = True
        self._axis_selected_value = str(axis_id or "").strip()

    def _on_param_action(self, kind: str, group: str) -> None:
        self._events.append(HipParamAction(kind=str(kind), group=str(group)))

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------

    def read_inputs(self) -> HipUiInputs:
        axis_selected = ""
        if self._cmbAxis is not None:
            try:
                axis_selected = str(self._cmbAxis.currentText() or "").strip()
            except Exception:
                axis_selected = ""

        events = list(self._events)
        self._events.clear()
        estop_reset_clicked = bool(self._estop_reset_clicked)
        resync_clicked = bool(self._resync_clicked)
        axis_selection_changed = bool(self._axis_selection_changed)
        if axis_selection_changed and self._axis_selected_value:
            axis_selected = self._axis_selected_value
        self._estop_reset_clicked = False
        self._resync_clicked = False
        self._axis_selection_changed = False
        self._axis_selected_value = ""

        param_values: dict[str, dict[str, float]] = {}
        for group in _PARAM_WIDGETS.keys():
            param_values[group] = self._param_binder.read_group_values(group)

        return HipUiInputs(
            axis_selected=axis_selected,
            axis_selection_changed=axis_selection_changed,
            estop_reset_clicked=estop_reset_clicked,
            resync_clicked=resync_clicked,
            param_actions=events,
            param_values=param_values,
        )

    # ------------------------------------------------------------------
    # Apply VM
    # ------------------------------------------------------------------

    def apply(self, vm: HipViewModel) -> None:
        self.apply_tick_text(vm.tick_text)
        self._set_joy_properties(vm.joy_deadman, vm.joy_select_hip)
        self._apply_attach_state(vm)
        if vm.attach_state is not None and not bool(vm.attach_state.attached):
            self._apply_joy_speed(float(vm.joy_soll_speed))
            return
        self._apply_drive_status(vm)
        self._apply_banner(vm)
        self._apply_header_dots(vm)
        self._apply_estop_state(vm)
        self._apply_readouts(vm)
        self._apply_joy_speed(float(vm.joy_soll_speed))
        self._apply_cut_markers(vm)
        self._apply_params(vm)

    def apply_startup_state(self) -> None:
        self.apply_tick_text("--")
        self._set_all_estop_unknown()
        self._set_joy_properties(False, False)
        self._apply_joy_speed(0.0)

    def apply_tick_text(self, text: str) -> None:
        if self._txtTick is None:
            return
        set_text(self._txtTick, str(text))

    def apply_online_state(self, state: str | None) -> None:
        if state is None:
            return
        self._set_dot("dotHdrOnline", state)

    def _set_joy_properties(self, deadman: bool, select_hip: bool) -> None:
        # Joy UI reflection: QSS uses joy_deadman/joy_select dynamic properties.
        if self._frame_footer is not None:
            set_state_property(
                self._frame_footer,
                "true" if bool(deadman) else "false",
                prop="joy_deadman",
            )
        if self._frame_header is not None:
            set_state_property(
                self._frame_header,
                "true" if bool(select_hip) else "false",
                prop="joy_select",
            )

    def _apply_joy_speed(self, soll_speed: float) -> None:
        # sldVelCmd is display-only; updates are programmatic with signals blocked.
        if self._sld_vel_cmd is None:
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
            min_v = int(self._sld_vel_cmd.minimum())
            max_v = int(self._sld_vel_cmd.maximum())
        except Exception:
            min_v = 0
            max_v = 0

        if min_v >= 0 or max_v <= 0:
            scale = max(abs(min_v), abs(max_v), 1000)
            min_v = -scale
            max_v = scale
            update_slider(self._sld_vel_cmd, minimum=min_v, maximum=max_v)
        else:
            scale = max(abs(min_v), abs(max_v))
            if scale <= 0:
                scale = 1000

        value = int(round(v * scale))
        if value < min_v:
            value = min_v
        elif value > max_v:
            value = max_v
        update_slider(self._sld_vel_cmd, value=value)


    # ------------------------------------------------------------------
    # Apply helpers
    # ------------------------------------------------------------------

    def _apply_attach_state(self, vm: HipViewModel) -> None:
        if vm.attach_combo is not None and self._cmbAxis is not None:
            items = list(vm.attach_combo.items or [])
            cur = str(vm.attach_combo.current or "")
            existing = [self._cmbAxis.itemText(i) for i in range(self._cmbAxis.count())]
            if existing != items or (cur and self._cmbAxis.currentText().strip() != cur):
                self._suppress_axis_signal = True
                was = self._cmbAxis.blockSignals(True)
                try:
                    if existing != items:
                        self._cmbAxis.clear()
                        self._cmbAxis.addItems(items)
                    if cur and self._cmbAxis.currentText().strip() != cur:
                        self._cmbAxis.setCurrentText(cur)
                finally:
                    self._cmbAxis.blockSignals(was)
                    self._suppress_axis_signal = False
            set_enabled(self._cmbAxis, bool(vm.attach_combo.enabled))

        if vm.attach_state is None:
            return

        if self._tabs_main is not None and vm.attach_state.tabs_enabled is not None:
            set_enabled(self._tabs_main, bool(vm.attach_state.tabs_enabled))

        btn_setup = self._find_button("btnSetupToggle")
        btnReset = self._find_button("btnReset")
        btn_rec = self._find_button("btnRecover")
        if btn_setup is not None:
            set_enabled(btn_setup, bool(vm.attach_state.setup_enabled))
        if btnReset is not None:
            set_enabled(btnReset, bool(vm.attach_state.main_amp_reset_enabled))
        if btn_rec is not None:
            set_enabled(btn_rec, False)

        if self._btn_diag_resync is not None:
            set_enabled(self._btn_diag_resync, bool(vm.attach_state.resync_enabled))

        if self._btn_estop_reset is not None and vm.attach_state.estop_reset_enabled is not None:
            set_enabled(self._btn_estop_reset, bool(vm.attach_state.estop_reset_enabled))

        if not bool(vm.attach_state.attached):
            self._clear_for_unattached()

    def _apply_drive_status(self, vm: HipViewModel) -> None:
        ds = vm.drive_status
        if ds is None:
            return
        if self._txt_main_amp_status is not None:
            set_text(self._txt_main_amp_status, str(ds.main_text))
        if self._txt_slave_amp_status is not None:
            set_text(self._txt_slave_amp_status, str(ds.slave_text))

    def _apply_banner(self, vm: HipViewModel) -> None:
        if vm.banner is None:
            return
        bg, fg = BANNER_COLORS.get(vm.banner.estate, ("#F9E547", "#000000"))
        for w in (self._txt_hdr_banner_left, self._txt_hdr_banner_right):
            if w is None:
                continue
            set_text(w, vm.banner.estate)
            w.setStyleSheet(f"background-color: {bg}; color: {fg}; font-weight: 700;")

    def _apply_header_dots(self, vm: HipViewModel) -> None:
        if vm.header_dots is None:
            return
        self._set_dot("dotHdrOnline", vm.header_dots.online_state)
        self._set_dot("dotHdrReady", vm.header_dots.ready_state)
        self._set_dot("dotHdrFbt", vm.header_dots.fbt_state)
        self._set_dot("dotHdrBrake1", vm.header_dots.brk1_state)
        self._set_dot("dotHdrBrake2", vm.header_dots.brk2_state)

    def _apply_estop_state(self, vm: HipViewModel) -> None:
        es = vm.estop_state
        if es is None:
            return
        for dot, state in (es.dots or {}).items():
            self._set_dot(str(dot), state)
        if self._btn_estop_reset is not None:
            set_enabled(self._btn_estop_reset, bool(es.reset_enabled))

        # Checkboxes (read-only)
        for key, cb in (self._estop_checks or {}).items():
            v = bool(es.checkbox_states.get(key, False))
            set_checked(cb, v, block_signals=True)
            if es.profile_changed:
                try:
                    f = cb.font()
                    f.setBold(key in es.active_keys)
                    cb.setFont(f)
                except Exception:
                    pass

    def _apply_readouts(self, vm: HipViewModel) -> None:
        ro = vm.readouts
        if ro is None:
            return

        if self._txtPos is not None:
            set_text(self._txtPos, ro.pos_text)
        if self._txtVel is not None:
            set_text(self._txtVel, ro.vel_text)
        if self._txtAmp is not None:
            set_text(self._txtAmp, ro.amp_text)
        if self._txtTemp is not None:
            set_text(self._txtTemp, ro.temp_text)

        if self._txt_guider_range_min is not None:
            set_text(self._txt_guider_range_min, ro.guider_min_text)
        if self._txt_guider_range_max is not None:
            set_text(self._txt_guider_range_max, ro.guider_max_text)
        if self._txt_guider_range_val is not None:
            set_text(self._txt_guider_range_val, ro.guider_val_text)
        if self._txt_guider_speed is not None:
            set_text(self._txt_guider_speed, ro.guider_speed_text)

        if self._sld_vel_cmd is not None:
            update_slider(
                self._sld_vel_cmd,
                minimum=ro.vel_cmd_min,
                maximum=ro.vel_cmd_max,
                value=ro.vel_cmd_val,
            )
        if self._sld_limit_range is not None:
            update_slider(
                self._sld_limit_range,
                minimum=ro.limit_min,
                maximum=ro.limit_max,
                value=ro.limit_val,
            )
        if self._sld_guider_range is not None:
            update_slider(
                self._sld_guider_range,
                minimum=ro.guider_range_min,
                maximum=ro.guider_range_max,
                value=ro.guider_range_val,
            )
        if self._sld_guider_speed is not None:
            update_slider(
                self._sld_guider_speed,
                minimum=ro.guider_speed_min,
                maximum=ro.guider_speed_max,
                value=ro.guider_speed_val,
            )

    def _apply_cut_markers(self, vm: HipViewModel) -> None:
        cm = vm.cut_markers
        if cm is None:
            return
        if self._txtCutTime is not None:
            set_text(self._txtCutTime, cm.cut_time_text)
        if self._txtCutPos is not None:
            set_text(self._txtCutPos, cm.cut_pos_text)
        if self._txtCutVel is not None:
            set_text(self._txtCutVel, cm.cut_vel_text)
        if self._txtPosdiff is not None:
            set_text(self._txtPosdiff, cm.posdiff_text)

    def _apply_params(self, vm: HipViewModel) -> None:
        if vm.param_ui is not None:
            self._apply_modal_param_lock(vm.param_ui.modal_lock_active, vm.param_ui.modal_lock_group)

            for group, gstate in (vm.param_ui.groups or {}).items():
                self._set_param_group_enabled(group, bool(gstate.fields_enabled))
                self._set_param_button_state(group, gstate.buttons)

        if vm.param_values:
            self._param_binder.apply_param_values(
                vm.param_values,
                freeze_group=str(vm.param_freeze_group or ""),
                skip_focused=True,
                block_signals=True,
            )

        if vm.param_writeback_values and vm.param_writeback_group:
            self._param_binder.apply_param_values(
                vm.param_writeback_values,
                freeze_group=str(vm.param_writeback_group or ""),
                skip_focused=False,
                block_signals=True,
            )
            if vm.param_writeback_message:
                QMessageBox.information(
                    self.win,
                    "Position limits adjusted",
                    str(vm.param_writeback_message),
                )

        if vm.param_commit_dialog is not None:
            dlg = vm.param_commit_dialog
            if str(dlg.level).lower() == "warning":
                QMessageBox.warning(self.win, str(dlg.title), str(dlg.message))
            else:
                QMessageBox.information(self.win, str(dlg.title), str(dlg.message))

        if vm.limit_values:
            self._param_binder.apply_limit_values(
                vm.limit_values,
                format_value=lambda v: fmt_f_unit(v, "m", ndigits=2).replace(".", ","),
            )

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _init_param_inputs(self) -> None:
        self._param_binder.init_param_inputs()

    def _find_button(self, object_name: str) -> QPushButton | None:
        try:
            return self._wcache.button(object_name)
        except Exception:
            w = self.win.findChild(QPushButton, object_name)
            return w if isinstance(w, QPushButton) else None

    def _find_line_edit(self, object_name: str) -> QLineEdit | None:
        try:
            return self._wcache.line_edit(object_name)
        except Exception:
            w = self.win.findChild(QLineEdit, object_name)
            return w if isinstance(w, QLineEdit) else None

    def _set_dot(self, object_name: str, state) -> None:
        if not object_name:
            return
        try:
            ww = self._wcache.widget(object_name)
            if ww is not None:
                set_state_property(ww, state)
                return
        except Exception:
            pass
        set_state_by_object_name(self.win, object_name, state)

    def _set_all_estop_unknown(self) -> None:
        for spec in ESTOP_SPECS.values():
            if spec.dot:
                self._set_dot(spec.dot, "warn")

    def _clear_for_unattached(self) -> None:
        keep = [self._txtTick] if self._txtTick is not None else []
        clear_line_edits(self.win, keep=keep, text="")
        if self._txtTick is not None:
            set_text(self._txtTick, "--")

        for w in (
            self._txt_main_amp_status,
            self._txt_slave_amp_status,
            self._txt_hdr_banner_left,
            self._txt_hdr_banner_right,
        ):
            if w is not None:
                set_text(w, "")

        neutralize_dots(self._set_dot, ("dotHdrOnline", "dotHdrReady", "dotHdrFbt", "dotHdrBrake1", "dotHdrBrake2"))
        neutralize_dots(self._set_dot, [s.dot for s in ESTOP_SPECS.values() if s.dot])
        uncheck_checkboxes(getattr(self, "_estop_checks", {}).values())

    def _apply_modal_param_lock(self, active: bool, group: str) -> None:
        tabs = self._tabs_main
        if active and not self._modal_locked:
            self._modal_prev_enabled = {}

            if tabs is not None:
                self._modal_prev_tabbar_enabled = bool(tabs.tabBar().isEnabled())
                set_enabled(tabs.tabBar(), False)

            for w in self._modal_widgets:
                if isinstance(w, (QPushButton, QLineEdit)):
                    self._modal_prev_enabled[w] = bool(w.isEnabled())
                    set_enabled(w, False)

            allow: list[QWidget] = []
            for _k, obj_name in _PARAM_WIDGETS.get(group, {}).items():
                le = self._find_line_edit(obj_name)
                if le is not None:
                    allow.append(le)

            wiring = {
                "pos": ("btnPosWrite", "btnPosCancel"),
                "vel": ("btnVelWrite", "btnVelCancel"),
                "filter": ("btnFilterWrite", "btnFilterCancel"),
                "guider": ("btnGuiderWrite", "btnGuiderCancel"),
            }
            if group in wiring:
                bw = self._find_button(wiring[group][0])
                bc = self._find_button(wiring[group][1])
                if bw is not None:
                    allow.append(bw)
                if bc is not None:
                    allow.append(bc)

            for w in allow:
                if isinstance(w, QLineEdit):
                    set_enabled_repolish(w, True)
                else:
                    set_enabled(w, True)

            self._modal_locked = True
            return

        if (not active) and self._modal_locked:
            for w, was_enabled in list(self._modal_prev_enabled.items()):
                try:
                    if isinstance(w, QLineEdit):
                        set_enabled_repolish(w, bool(was_enabled))
                    else:
                        set_enabled(w, bool(was_enabled))
                except RuntimeError:
                    pass
            self._modal_prev_enabled.clear()

            if tabs is not None and self._modal_prev_tabbar_enabled is not None:
                set_enabled(tabs.tabBar(), bool(self._modal_prev_tabbar_enabled))
            self._modal_prev_tabbar_enabled = None
            self._modal_locked = False

    def _set_param_group_enabled(self, group: str, enabled: bool) -> None:
        mapping = _PARAM_WIDGETS.get(group, {})
        for _key, obj_name in mapping.items():
            le = self._find_line_edit(obj_name)
            if le is None:
                continue
            set_enabled_repolish(le, bool(enabled))

    def _set_param_button_state(self, group: str, buttons) -> None:
        wiring = {
            "pos": ("btnPosEdit", "btnPosWrite", "btnPosCancel"),
            "vel": ("btnVelEdit", "btnVelWrite", "btnVelCancel"),
            "filter": ("btnFilterEdit", "btnFilterWrite", "btnFilterCancel"),
            "guider": ("btnGuiderEdit", "btnGuiderWrite", "btnGuiderCancel"),
        }
        if group not in wiring:
            return
        b_edit, b_write, b_cancel = wiring[group]
        be = self._find_button(b_edit)
        bw = self._find_button(b_write)
        bc = self._find_button(b_cancel)
        if be is not None:
            set_enabled(be, bool(buttons.edit_enabled))
        if bw is not None:
            set_enabled(bw, bool(buttons.write_enabled))
        if bc is not None:
            set_enabled(bc, bool(buttons.cancel_enabled))
