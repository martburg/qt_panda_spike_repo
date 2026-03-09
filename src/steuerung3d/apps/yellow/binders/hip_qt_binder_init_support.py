from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLineEdit, QPushButton, QWidget

from steuerung3d.protocol.estop_bits import ESTOP_SPECS

from ..domain.yellow_maps import LIMIT_WIDGETS as _LIMIT_WIDGETS, PARAM_WIDGETS as _PARAM_WIDGETS
from ..panels.hip.hip_banner_render import HipBannerBindings
from ..panels.hip.hip_cut_markers_render import HipCutMarkersBindings
from ..panels.hip.hip_drive_status_render import HipDriveStatusBindings
from ..panels.hip.hip_estop_render import HipEstopBindings
from ..panels.hip.hip_header_dots_render import HipHeaderDotsBindings
from ..panels.hip.hip_readouts_render import HipReadoutsBindings
from ..panels.hip.hip_sliders_render import HipSlidersBindings
from ..qtutil.modal_lock import ModalLock
from ..qtutil.param_ui_apply import ParamUiBindings
from ..qtutil.param_widget_binder import ParamWidgetBinder
from ..qtutil.ui_format import fmt_f_unit_de
from ..qtutil.ui_update import set_enabled, set_enabled_repolish
from ..qtutil.widget_cache import WidgetCache
from .hip_qt_widgets import HipQtWidgets

if TYPE_CHECKING:
    from .hip_qt_binder import HipQtBinder


def setup_widget_cache(self: "HipQtBinder") -> None:
    self._wcache = WidgetCache(self.win)
    self._widgets = HipQtWidgets.from_cache(self._wcache)
    self._param_binder = ParamWidgetBinder(
        self.win,
        self.log,
        _PARAM_WIDGETS,
        _LIMIT_WIDGETS,
        cache=self._wcache,
    )


def discover_widgets(self: "HipQtBinder") -> None:
    self._tabs_main = self._widgets.tabs_main
    self._cmbAxis = self._widgets.cmb_axis
    self._frame_footer = self._widgets.frame_footer
    self._frame_header = self._widgets.frame_header
    self._txtTick = self._widgets.txt_tick
    self._txt_hdr_banner_left = self._wcache.line_edit("txtHdrBannerLeft")
    self._txt_hdr_banner_right = self._wcache.line_edit("txtHdrBannerRight")
    self._txt_main_amp_status = self._wcache.line_edit("txtMainAmpStatus")
    self._txt_slave_amp_status = self._wcache.line_edit("txtSlaveAmpStatus")
    self._txtPos = self._wcache.line_edit("txtPos")
    self._txtVel = self._wcache.line_edit("txtVel")
    self._txtAmp = self._wcache.line_edit("txtAmp")
    self._txtTemp = self._wcache.line_edit("txtTemp")
    self._txtLimitHardMin = self._wcache.line_edit("txtLimitHardMin")
    self._txtLimitUserMin = self._wcache.line_edit("txtLimitUserMin")
    self._txtLimitUserMax = self._wcache.line_edit("txtLimitUserMax")
    self._txtLimitHardMax = self._wcache.line_edit("txtLimitHardMax")
    self._txtCutPos = self._wcache.line_edit("txtCutPos")
    self._txtCutVel = self._wcache.line_edit("txtCutVel")
    self._txtCutTime = self._wcache.line_edit("txtCutTime")
    self._txtPosdiff = self._wcache.line_edit("txtPosdiff")
    self._txt_guider_range_min = self._wcache.line_edit("txtGuiderRangeMin")
    self._txt_guider_range_max = self._wcache.line_edit("txtGuiderRangeMax")
    self._txt_guider_range_val = self._wcache.line_edit("txtGuiderRangeValue")
    self._txt_guider_speed = self._wcache.line_edit("txtGuiderSpeed")
    self._txtGuiderPosMin = self._wcache.line_edit("txtGPosMin_3")
    self._txtGuiderPosMax = self._wcache.line_edit("txtGPosMax_2")
    self._txtGuiderPitch = self._wcache.line_edit("txtPitch_2")
    self._sld_vel_cmd = self._widgets.sld_vel_cmd
    self._sld_limit_range = self._wcache.slider("sldLimitRange")
    self._sld_guider_range = self._wcache.slider("sldGuiderRange")
    self._sld_guider_speed = self._wcache.slider("sldGuiderSpeed")
    self._btn_estop_reset = self._widgets.btn_estop_reset
    self._btn_diag_resync = self._widgets.btn_diag_resync
    self._btn_main_reset = self._wcache.button("btnMainReset")
    self._btn_guider_reset = self._wcache.button("btnGuiderReset")


def discover_estop_checkboxes(self: "HipQtBinder") -> None:
    self._estop_checks = {}
    for spec in ESTOP_SPECS.values():
        if not spec.checkbox:
            continue
        cb = self._wcache.checkbox(spec.checkbox)
        if cb is not None:
            cb.setEnabled(False)
            self._estop_checks[spec.key] = cb


def disable_action_buttons(self: "HipQtBinder") -> None:
    for w in (
        self._btn_estop_reset,
        self._btn_diag_resync,
        getattr(self, "_btn_main_reset", None),
        getattr(self, "_btn_guider_reset", None),
    ):
        if w is not None:
            set_enabled(w, False)


def setup_modal_and_params(self: "HipQtBinder") -> None:
    try:
        modal_widgets = [
            w for w in self.win.findChildren(QWidget) if isinstance(w, (QPushButton, QLineEdit))
        ]
    except Exception:
        modal_widgets = []
    self._modal_lock = ModalLock(
        widgets=modal_widgets,
        tabs=self._tabs_main,
        enable_widget=set_enabled,
        enable_line_edit=set_enabled_repolish,
    )
    self._param_ui_bindings = ParamUiBindings(
        win=self.win,
        modal_lock=self._modal_lock,
        param_binder=self._param_binder,
        find_line_edit=self._find_line_edit,
        find_button=self._find_button,
        format_limit_value=lambda v: fmt_f_unit_de(v, unit="m", ndigits=2, empty="--"),
    )
    self._param_binder.init_param_inputs()


def build_bindings(self: "HipQtBinder") -> None:
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
    self._sliders_bindings = HipSlidersBindings(
        sld_vel_cmd=self._sld_vel_cmd,
        sld_limit_range=self._sld_limit_range,
        sld_guider_range=self._sld_guider_range,
        sld_guider_speed=self._sld_guider_speed,
    )


def log_binder_missing(self: "HipQtBinder") -> None:
    expected: dict[str, object] = {
        "cmbAxis": self._cmbAxis,
        "txtTick": self._txtTick,
        "txtPos": self._txtPos,
        "txtVel": self._txtVel,
        "txtAmp": self._txtAmp,
        "txtTemp": self._txtTemp,
        "txtLimitHardMin": self._txtLimitHardMin,
        "txtLimitUserMin": self._txtLimitUserMin,
        "txtLimitUserMax": self._txtLimitUserMax,
        "txtLimitHardMax": self._txtLimitHardMax,
        "txtCutPos": self._txtCutPos,
        "txtCutVel": self._txtCutVel,
        "txtCutTime": self._txtCutTime,
        "txtPosdiff": self._txtPosdiff,
        "txtGuiderRangeMin": self._txt_guider_range_min,
        "txtGuiderRangeMax": self._txt_guider_range_max,
        "txtGuiderRangeValue": self._txt_guider_range_val,
        "txtGuiderSpeed": self._txt_guider_speed,
        "txtPosMin": self._txtGuiderPosMin,
        "txtPosMax": self._txtGuiderPosMax,
        "txtPitch": self._txtGuiderPitch,
        "sldVelCmd": self._sld_vel_cmd,
        "sldLimitRange": self._sld_limit_range,
        "sldGuiderRange": self._sld_guider_range,
        "sldGuiderSpeed": self._sld_guider_speed,
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
