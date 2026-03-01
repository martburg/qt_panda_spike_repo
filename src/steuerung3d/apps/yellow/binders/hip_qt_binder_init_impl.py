from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QAbstractSlider,
    QCheckBox,
    QComboBox,
    QFrame,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QWidget,
)

from ..qtutil.ui_panel_state import clear_line_edits, neutralize_dots, uncheck_checkboxes
from ..qtutil.param_widget_binder import ParamWidgetBinder
from ..qtutil.modal_lock import ModalLock
from ..qtutil.param_ui_apply import ParamUiBindings
from ..qtutil.ui_update import (
    set_enabled,
    set_enabled_repolish,
    set_state_by_object_name,
    set_state_property,
)
from ..qtutil.widget_cache import WidgetCache
from ..qtutil.ui_format import fmt_f_unit_de
from ..qtutil.ui_contract import log_missing_optional_once, log_missing_required_once
from ..qtutil.binder_helpers import safe_set_text
from ..domain.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS, LIMIT_WIDGETS as _LIMIT_WIDGETS
from ..panels.hip.hip_banner_render import HipBannerBindings
from ..panels.hip.hip_estop_render import HipEstopBindings
from ..panels.hip.hip_header_dots_render import HipHeaderDotsBindings
from ..panels.hip.hip_cut_markers_render import HipCutMarkersBindings
from ..panels.hip.hip_drive_status_render import HipDriveStatusBindings
from ..panels.hip.hip_readouts_render import HipReadoutsBindings
from ..panels.hip.hip_sliders_render import HipSlidersBindings
from steuerung3d.protocol.estop_bits import ESTOP_SPECS

if TYPE_CHECKING:
    from .hip_qt_binder import HipQtBinder


def post_init(self: "HipQtBinder") -> None:
    self._wcache = WidgetCache(self.win)

    # Param binder (Parameter tab)
    self._param_binder = ParamWidgetBinder(
        self.win,
        self.log,
        _PARAM_WIDGETS,
        _LIMIT_WIDGETS,
        cache=self._wcache,
    )

    # --- Core widgets
    self._tabs_main: QTabWidget | None = self._wcache.get(QTabWidget, "tabsMain")
    self._cmbAxis: QComboBox | None = self._wcache.combo_box("cmbAxis")
    # Footer frame (exists in yellow3_merged.ui as name="frameFooter")
    self._frame_footer: QFrame | None = self._wcache.get(QFrame, "frameFooter")
    self._frame_header: QFrame | None = self._wcache.get(QFrame, "frameHeader")

    # Header + tick
    self._txtTick: QLineEdit | None = self._wcache.line_edit("txtTick")
    self._txt_hdr_banner_left: QLineEdit | None = self._wcache.line_edit("txtHdrBannerLeft")
    self._txt_hdr_banner_right: QLineEdit | None = self._wcache.line_edit("txtHdrBannerRight")

    # Drive status
    self._txt_main_amp_status: QLineEdit | None = self._wcache.line_edit("txtMainAmpStatus")
    self._txt_slave_amp_status: QLineEdit | None = self._wcache.line_edit("txtSlaveAmpStatus")

    # --- Readouts (main)
    self._txtPos: QLineEdit | None = self._wcache.line_edit("txtPos")
    self._txtVel: QLineEdit | None = self._wcache.line_edit("txtVel")
    self._txtAmp: QLineEdit | None = self._wcache.line_edit("txtAmp")
    self._txtTemp: QLineEdit | None = self._wcache.line_edit("txtTemp")

    # --- Limit readouts (these exist in UI, but not yet wired into a bindings dataclass)
    self._txtLimitHardMin: QLineEdit | None = self._wcache.line_edit("txtLimitHardMin")
    self._txtLimitUserMin: QLineEdit | None = self._wcache.line_edit("txtLimitUserMin")
    self._txtLimitUserMax: QLineEdit | None = self._wcache.line_edit("txtLimitUserMax")
    self._txtLimitHardMax: QLineEdit | None = self._wcache.line_edit("txtLimitHardMax")

    # --- Cut markers
    self._txtCutPos: QLineEdit | None = self._wcache.line_edit("txtCutPos")
    self._txtCutVel: QLineEdit | None = self._wcache.line_edit("txtCutVel")
    self._txtCutTime: QLineEdit | None = self._wcache.line_edit("txtCutTime")
    # legacy UI uses txtPosdiff (lowercase d)
    self._txtPosdiff: QLineEdit | None = self._wcache.line_edit("txtPosdiff")

    # --- Guider range (wired by HipReadoutsBindings today)
    self._txt_guider_range_min: QLineEdit | None = self._wcache.line_edit("txtGuiderRangeMin")
    self._txt_guider_range_max: QLineEdit | None = self._wcache.line_edit("txtGuiderRangeMax")
    self._txt_guider_range_val: QLineEdit | None = self._wcache.line_edit("txtGuiderRangeValue")
    self._txt_guider_speed: QLineEdit | None = self._wcache.line_edit("txtGuiderSpeed")

    # --- Guider extras (discovered + logged; not wired into bindings yet)
    self._txtGuiderPosMin = self._wcache.line_edit("txtGPosMin_3")
    self._txtGuiderPosMax = self._wcache.line_edit("txtGPosMax_2")
    self._txtGuiderPitch  = self._wcache.line_edit("txtPitch_2")

    # --- Sliders
    self._sld_vel_cmd: QAbstractSlider | None = self._wcache.slider("sldVelCmd")
    self._sld_limit_range: QAbstractSlider | None = self._wcache.slider("sldLimitRange")
    self._sld_guider_range: QAbstractSlider | None = self._wcache.slider("sldGuiderRange")
    self._sld_guider_speed: QAbstractSlider | None = self._wcache.slider("sldGuiderSpeed")

    # Buttons
    self._btn_estop_reset: QPushButton | None = self._wcache.button("btnEStopReset")
    self._btn_diag_resync: QPushButton | None = self._wcache.button("btnDiagResync")
    self._btn_main_reset: QPushButton | None = self._wcache.button("btnMainReset")
    self._btn_guider_reset: QPushButton | None = self._wcache.button("btnGuiderReset")

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
    if getattr(self, "_btn_main_reset", None) is not None:
        set_enabled(self._btn_main_reset, False)
    if getattr(self, "_btn_guider_reset", None) is not None:
        set_enabled(self._btn_guider_reset, False)

    # Modal lock helpers (best-effort)
    try:
        modal_widgets = [w for w in self.win.findChildren(QWidget) if isinstance(w, (QPushButton, QLineEdit))]
    except Exception:
        modal_widgets = []
    self._modal_lock = ModalLock(
        widgets=modal_widgets,
        tabs=self._tabs_main,
        enable_widget=set_enabled,
        enable_line_edit=set_enabled_repolish,
    )

    # Param UI bindings
    self._param_ui_bindings = ParamUiBindings(
        win=self.win,
        modal_lock=self._modal_lock,
        param_binder=self._param_binder,
        find_line_edit=self._find_line_edit,
        find_button=self._find_button,
        format_limit_value=lambda v: fmt_f_unit_de(v, unit="m", ndigits=2, empty="--"),
    )

    # Param inputs/validators
    self._param_binder.init_param_inputs()

    # Build render bindings
    _build_bindings(self)

    # Emit binder discovery status (INFO)
    _log_binder_missing(self)

    # Keep existing contract checks (optional)
    log_missing_required_once(self.log, self._wcache, [(QComboBox, "cmbAxis"), (QLineEdit, "txtTick")], context="hi_p:required")

    self._wire_signals()


def _build_bindings(self: "HipQtBinder") -> None:
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

    # IMPORTANT: Only pass kwargs that HipReadoutsBindings actually supports.
    self._readouts_bindings = HipReadoutsBindings(
        txt_pos=self._txtPos,
        txt_vel=self._txtVel,
        txt_amp=self._txtAmp,
        txt_temp=self._txtTemp,
        txt_guider_range_min=self._txt_guider_range_min,
        txt_guider_range_max=self._txt_guider_range_max,
        txt_guider_range_val=self._txt_guider_range_val,
        txt_guider_speed=self._txt_guider_speed,
    )

    self.log.info(
        "hi_p: dbg bindings readouts txt_pos=%s txt_vel=%s",
        self._readouts_bindings.txt_pos if self._readouts_bindings else None,
        self._readouts_bindings.txt_vel if self._readouts_bindings else None,
    )   

    # IMPORTANT: Only pass kwargs that HipSlidersBindings actually supports.
    self._sliders_bindings = HipSlidersBindings(
        sld_vel_cmd=self._sld_vel_cmd,
        sld_limit_range=self._sld_limit_range,
        sld_guider_range=self._sld_guider_range,
        sld_guider_speed=self._sld_guider_speed,
    )


def _log_binder_missing(self: "HipQtBinder") -> None:
    expected: dict[str, object] = {
        # main
        "cmbAxis": self._cmbAxis,
        "txtTick": self._txtTick,
        "txtPos": self._txtPos,
        "txtVel": self._txtVel,
        "txtAmp": self._txtAmp,
        "txtTemp": self._txtTemp,
        # limits + cut
        "txtLimitHardMin": self._txtLimitHardMin,
        "txtLimitUserMin": self._txtLimitUserMin,
        "txtLimitUserMax": self._txtLimitUserMax,
        "txtLimitHardMax": self._txtLimitHardMax,
        "txtCutPos": self._txtCutPos,
        "txtCutVel": self._txtCutVel,
        "txtCutTime": self._txtCutTime,
        "txtPosdiff": self._txtPosdiff,
        # guider
        "txtGuiderRangeMin": self._txt_guider_range_min,
        "txtGuiderRangeMax": self._txt_guider_range_max,
        "txtGuiderRangeValue": self._txt_guider_range_val,
        "txtGuiderSpeed": self._txt_guider_speed,
        "txtPosMin": self._txtGuiderPosMin,
        "txtPosMax": self._txtGuiderPosMax,
        "txtPitch": self._txtGuiderPitch,
        # sliders
        "sldVelCmd": self._sld_vel_cmd,
        "sldLimitRange": self._sld_limit_range,
        "sldGuiderRange": self._sld_guider_range,
        "sldGuiderSpeed": self._sld_guider_speed,
        # buttons
        "btnEStopReset": self._btn_estop_reset,
        "btnDiagResync": self._btn_diag_resync,
        "btnMainReset": getattr(self, "_btn_main_reset", None),
        "btnGuiderReset": getattr(self, "_btn_guider_reset", None),
    }
    missing = sorted([k for k, v in expected.items() if v is None])
    if missing:
        self.log.info("hi_p: binder missing widgets: %s", ", ".join(missing))
    else:
        self.log.info("hi_p: binder widget discovery OK")


# ------------------------------------------------------------------
# Signal wiring / input capture
# ------------------------------------------------------------------

def wire_signals(self: "HipQtBinder") -> None:
    if self._cmbAxis is not None:
        self._cmbAxis.currentTextChanged.connect(self._on_axis_selected)
    if self._btn_estop_reset is not None:
        self._btn_estop_reset.clicked.connect(self._on_estop_reset_clicked)
    if self._btn_diag_resync is not None:
        self._btn_diag_resync.clicked.connect(self._on_resync_clicked)
    if getattr(self, "_btn_main_reset", None) is not None:
        self._btn_main_reset.clicked.connect(self._on_main_reset_clicked)
    if getattr(self, "_btn_guider_reset", None) is not None:
        self._btn_guider_reset.clicked.connect(self._on_guider_reset_clicked)

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


def find_button(self: "HipQtBinder", object_name: str) -> QPushButton | None:
    return self._wcache.button(object_name)


def find_line_edit(self: "HipQtBinder", object_name: str) -> QLineEdit | None:
    return self._wcache.line_edit(object_name)


def require_widget(widget: QWidget | None, object_name: str) -> QWidget:
    if widget is None:
        raise RuntimeError(f"UI is missing widget named '{object_name}'")
    return widget


def set_dot(self: "HipQtBinder", object_name: str, state) -> None:
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


def set_all_estop_unknown(self: "HipQtBinder") -> None:
    for spec in ESTOP_SPECS.values():
        if spec.dot:
            self._set_dot(spec.dot, "warn")


def clear_for_unattached(self: "HipQtBinder") -> None:
    keep = [self._txtTick] if self._txtTick is not None else []
    clear_line_edits(self.win, keep=keep, text="")
    safe_set_text(self._txtTick, "--")

    for w in (
        self._txt_main_amp_status,
        self._txt_slave_amp_status,
        self._txt_hdr_banner_left,
        self._txt_hdr_banner_right,
    ):
        safe_set_text(w, "")

    neutralize_dots(self._set_dot, ("dotHdrOnline", "dotHdrReady", "dotHdrFbt", "dotHdrBrake1", "dotHdrBrake2"))
    neutralize_dots(self._set_dot, [s.dot for s in ESTOP_SPECS.values() if s.dot])
    uncheck_checkboxes(getattr(self, "_estop_checks", {}).values())