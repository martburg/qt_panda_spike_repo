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
    QPushButton,
    QTabWidget,
    QWidget,
)

from ..qtutil.ui_panel_state import clear_line_edits, neutralize_dots, uncheck_checkboxes
from ..qtutil.param_widget_binder import ParamWidgetBinder
from ..qtutil.modal_lock import ModalLock
from ..qtutil.param_ui_apply import ParamUiBindings, apply_param_ui
from ..qtutil.ui_update import (
    set_enabled,
    set_enabled_repolish,
    set_state_by_object_name,
    set_state_property,
    set_text,
    update_slider,
)
from ..qtutil.widget_cache import WidgetCache
from ..qtutil.ui_format import fmt_f_unit_de
from ..qtutil.ui_contract import log_missing_optional_once, log_missing_required_once
from ..domain.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS, LIMIT_WIDGETS as _LIMIT_WIDGETS
from ..domain.ui_format import fmt_f_unit
from ..panels.hip_banner_render import HipBannerBindings, apply_hip_banner
from ..panels.hip_estop_render import HipEstopBindings, apply_hip_estop
from ..panels.hip_header_dots_render import HipHeaderDotsBindings, apply_hip_header_dots
from ..panels.hip_cut_markers_render import HipCutMarkersBindings, apply_hip_cut_markers
from ..panels.hip_drive_status_render import HipDriveStatusBindings, apply_hip_drive_status
from ..panels.hip_readouts_render import HipReadoutsBindings, apply_hip_readouts
from ..panels.hip_sliders_render import HipSlidersBindings, apply_hip_sliders
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
    _banner_bindings: HipBannerBindings | None = None
    _estop_bindings: HipEstopBindings | None = None
    _header_dots_bindings: HipHeaderDotsBindings | None = None
    _cut_markers_bindings: HipCutMarkersBindings | None = None
    _drive_status_bindings: HipDriveStatusBindings | None = None
    _readouts_bindings: HipReadoutsBindings | None = None
    _sliders_bindings: HipSlidersBindings | None = None
    _modal_lock: ModalLock | None = None

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
        self._cmbAxis: QComboBox | None = self._wcache.combo_box("cmbAxis")

        # Header + tick
        self._txtTick: QLineEdit | None = self._wcache.line_edit("txtTick")
        self._txt_hdr_banner_left: QLineEdit | None = self._wcache.line_edit("txtHdrBannerLeft")
        self._txt_hdr_banner_right: QLineEdit | None = self._wcache.line_edit("txtHdrBannerRight")
        self._frame_header: QWidget | None = self._wcache.widget("frameHeader")
        self._frame_footer: QWidget | None = self._wcache.widget("frameFooter")

        # Drive status fields
        self._txt_main_amp_status: QLineEdit | None = self._wcache.line_edit("txtMainAmpStatus")
        self._txt_slave_amp_status: QLineEdit | None = self._wcache.line_edit("txtSlaveAmpStatus")

        # Readouts
        self._txtPos: QLineEdit | None = self._wcache.line_edit("txtPos")
        self._txtVel: QLineEdit | None = self._wcache.line_edit("txtVel")
        self._txtAmp: QLineEdit | None = self._wcache.line_edit("txtAmp")
        self._txtTemp: QLineEdit | None = self._wcache.line_edit("txtTemp")

        self._txtCutPos: QLineEdit | None = self._wcache.line_edit("txtCutPos")
        self._txtCutVel: QLineEdit | None = self._wcache.line_edit("txtCutVel")
        self._txtCutTime: QLineEdit | None = self._wcache.line_edit("txtCutTime")
        self._txtPosdiff: QLineEdit | None = self._wcache.line_edit("txtPosdiff")

        self._txt_guider_range_min: QLineEdit | None = self._wcache.line_edit("txtGuiderRangeMin")
        self._txt_guider_range_max: QLineEdit | None = self._wcache.line_edit("txtGuiderRangeMax")
        self._txt_guider_range_val: QLineEdit | None = self._wcache.line_edit("txtGuiderRangeValue")
        self._txt_guider_speed: QLineEdit | None = self._wcache.line_edit("txtGuiderSpeed")

        # Sliders
        self._sld_vel_cmd: QAbstractSlider | None = self._wcache.slider("sldVelCmd")
        self._sld_limit_range: QAbstractSlider | None = self._wcache.slider("sldLimitRange")
        self._sld_guider_range: QAbstractSlider | None = self._wcache.slider("sldGuiderRange")
        self._sld_guider_speed: QAbstractSlider | None = self._wcache.slider("sldGuiderSpeed")

        # Buttons
        self._btn_estop_reset: QPushButton | None = self._wcache.button("btnEStopReset")
        self._btn_diag_resync: QPushButton | None = self._wcache.button("btnDiagResync")

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
            cb = self._wcache.checkbox(spec.checkbox)
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
        self._modal_lock = ModalLock(
            widgets=self._modal_widgets,
            tabs=self._tabs_main,
            enable_widget=set_enabled,
            enable_line_edit=set_enabled_repolish,
        )

        # Param input validators (numeric)
        self._init_param_inputs()

        self._banner_bindings = HipBannerBindings(
            txt_hdr_banner_left=self._txt_hdr_banner_left,
            txt_hdr_banner_right=self._txt_hdr_banner_right,
        )
        self._estop_bindings = HipEstopBindings(
            btn_estop_reset=self._btn_estop_reset,
            estop_checks=dict(self._estop_checks or {}),
            set_dot=self._set_dot,
        )
        self._header_dots_bindings = HipHeaderDotsBindings(
            dot_hdr_online=self._wcache.widget("dotHdrOnline"),
            dot_hdr_ready=self._wcache.widget("dotHdrReady"),
            dot_hdr_fbt=self._wcache.widget("dotHdrFbt"),
            dot_hdr_brake1=self._wcache.widget("dotHdrBrake1"),
            dot_hdr_brake2=self._wcache.widget("dotHdrBrake2"),
        )
        self._cut_markers_bindings = HipCutMarkersBindings(
            txt_cut_time=self._txtCutTime,
            txt_cut_pos=self._txtCutPos,
            txt_cut_vel=self._txtCutVel,
            txt_posdiff=self._txtPosdiff,
        )
        self._drive_status_bindings = HipDriveStatusBindings(
            txt_main_amp_status=self._txt_main_amp_status,
            txt_slave_amp_status=self._txt_slave_amp_status,
        )
        self._readouts_bindings = HipReadoutsBindings(
            txt_pos=self._require_widget(self._txtPos, "txtPos"),
            txt_vel=self._require_widget(self._txtVel, "txtVel"),
            txt_amp=self._require_widget(self._txtAmp, "txtAmp"),
            txt_temp=self._require_widget(self._txtTemp, "txtTemp"),
            txt_guider_range_min=self._require_widget(self._txt_guider_range_min, "txtGuiderRangeMin"),
            txt_guider_range_max=self._require_widget(self._txt_guider_range_max, "txtGuiderRangeMax"),
            txt_guider_range_val=self._require_widget(self._txt_guider_range_val, "txtGuiderRangeValue"),
            txt_guider_speed=self._require_widget(self._txt_guider_speed, "txtGuiderSpeed"),
        )
        self._sliders_bindings = HipSlidersBindings(
            sld_vel_cmd=self._require_widget(self._sld_vel_cmd, "sldVelCmd"),
            sld_limit_range=self._require_widget(self._sld_limit_range, "sldLimitRange"),
            sld_guider_range=self._require_widget(self._sld_guider_range, "sldGuiderRange"),
            sld_guider_speed=self._require_widget(self._sld_guider_speed, "sldGuiderSpeed"),
        )

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
        self._apply_sliders(vm)
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
        if self._drive_status_bindings is None:
            return
        apply_hip_drive_status(self._drive_status_bindings, vm)

    def _apply_banner(self, vm: HipViewModel) -> None:
        if self._banner_bindings is None:
            return
        apply_hip_banner(self._banner_bindings, vm)

    def _apply_header_dots(self, vm: HipViewModel) -> None:
        if self._header_dots_bindings is None:
            return
        apply_hip_header_dots(self._header_dots_bindings, vm)

    def _apply_estop_state(self, vm: HipViewModel) -> None:
        if self._estop_bindings is None:
            return
        apply_hip_estop(self._estop_bindings, vm)

    def _apply_readouts(self, vm: HipViewModel) -> None:
        if self._readouts_bindings is None:
            return
        apply_hip_readouts(self._readouts_bindings, vm)

    def _apply_sliders(self, vm: HipViewModel) -> None:
        if self._sliders_bindings is None:
            return
        apply_hip_sliders(self._sliders_bindings, vm)

    def _apply_cut_markers(self, vm: HipViewModel) -> None:
        if self._cut_markers_bindings is None:
            return
        apply_hip_cut_markers(self._cut_markers_bindings, vm)

    def _apply_params(self, vm: HipViewModel) -> None:
        bindings = ParamUiBindings(
            win=self.win,
            modal_lock=self._modal_lock,
            param_binder=self._param_binder,
            find_line_edit=self._find_line_edit,
            find_button=self._find_button,
            format_limit_value=lambda v: fmt_f_unit_de(v, unit="m", ndigits=2, empty="--"),
        )
        apply_param_ui(bindings, vm)

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

    @staticmethod
    def _require_widget(widget: QWidget | None, object_name: str) -> QWidget:
        if widget is None:
            raise RuntimeError(f"UI is missing widget named '{object_name}'")
        return widget

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

