"""Qt-only binder for DenSi.

Responsibilities:
- Discover widgets.
- Wire signals for UI actions.
- Read UI inputs into DensiInputs.
- Apply DensiViewModel to the UI.

Business rules and state-machine logic must live in the runtime/engine.
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
    QWidget,
)

from ..controllers.ui_contract import log_missing_optional_once, log_missing_required_once
from ..controllers.ui_params import apply_param_values_to_line_edits
from ..controllers.ui_update import (
    set_checked,
    set_enabled,
    set_state_by_object_name,
    set_state_property,
    set_text,
    update_slider,
)
from ..controllers.widget_cache import WidgetCache
from ..controllers.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS, LIMIT_WIDGETS as _LIMIT_WIDGETS
from ..panels.densi_banner_render import DenSiBannerBindings, apply_densi_banner_vm
from ..panels.densi_cut_markers_render import DenSiCutMarkersBindings, apply_densi_cut_markers_vm
from ..panels.densi_estop_checkboxes import (
    DenSiEstopCheckboxBindings,
    discover_densi_estop_checkboxes,
    init_densi_estop_checkboxes,
    sync_densi_estop_checkboxes,
    wire_densi_estop_checkboxes,
)
from ..panels.densi_estop_dots_render import apply_densi_estop_dots_vm
from ..panels.densi_header_online_render import apply_densi_header_online_vm
from ..panels.densi_lifetick_render import apply_densi_lifetick_vm
from ..panels.densi_limits_vm import compute_densi_limits_vm
from ..panels.densi_limits_render import apply_densi_limits_vm
from ..panels.densi_readouts_render import DenSiReadoutsBindings, apply_densi_readouts_vm
from ..engines.densi_types2 import DensiInputs, DensiUiInputs, DensiEstopToggle
from ..engines.densi_viewmodel import DensiViewModel
from steuerung3d.protocol.estop_bits import decode_estop_word, iter_specs


@dataclass
class DenSiQtBinder:
    win: QWidget
    log: logging.Logger
    axis_ids: list[str]

    _ui_actions: DensiUiInputs = field(default_factory=DensiUiInputs)
    _estop_cb_bindings: DenSiEstopCheckboxBindings | None = None

    def __post_init__(self) -> None:
        self._wcache = WidgetCache(self.win)

        # Widgets
        self._txt_tick: QLineEdit | None = self.win.findChild(QLineEdit, "txt_tick")
        self._txt_hdr_banner_left: QLineEdit | None = self.win.findChild(QLineEdit, "txtHdrBannerLeft")
        self._txt_hdr_banner_right: QLineEdit | None = (
            self.win.findChild(QLineEdit, "txtHdrBannerRight")
            or self.win.findChild(QLineEdit, "txtHdrBannnerRight")
        )

        self._txt_pos: QLineEdit | None = self.win.findChild(QLineEdit, "txt_pos")
        self._txt_vel: QLineEdit | None = self.win.findChild(QLineEdit, "txt_vel")
        self._txt_amp: QLineEdit | None = self.win.findChild(QLineEdit, "txt_amp")
        self._txt_temp: QLineEdit | None = self.win.findChild(QLineEdit, "txt_temp")

        self._txt_cut_pos: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_pos")
        self._txt_cut_vel: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_vel")
        self._txt_cut_time: QLineEdit | None = self.win.findChild(QLineEdit, "txt_cut_time")
        self._txt_posdiff: QLineEdit | None = self.win.findChild(QLineEdit, "txt_posdiff")

        self._txt_guider_range_min: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeMin")
        self._txt_guider_range_max: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeMax")
        self._txt_guider_range_val: QLineEdit | None = self.win.findChild(QLineEdit, "txtGuiderRangeValue")
        self._txt_guider_speed: QLineEdit | None = (
            self.win.findChild(QLineEdit, "txtGuiderSpeed")
            or self.win.findChild(QLineEdit, "txtGuiderPos_2")
        )

        self._sld_vel_cmd: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldVelCmd")
        self._sld_limit_range: QAbstractSlider | None = self.win.findChild(QAbstractSlider, "sldLimitRange")

        self._btn_diag_resync: QPushButton | None = (
            self.win.findChild(QPushButton, "btnReSync")
            or self.win.findChild(QPushButton, "btnDiagResync")
        )
        self._btn_es_start: QPushButton | None = self.win.findChild(QPushButton, "btnESStart")

        self._btn_estop_all_set: QPushButton | None = self.win.findChild(QPushButton, "btnEStopAllSet")
        self._btn_estop_all_clear: QPushButton | None = self.win.findChild(QPushButton, "btnEStopAllClear")

        self._cmb_axis: QComboBox | None = self.win.findChild(QComboBox, "cmb_axis")

        self._b_readouts = DenSiReadoutsBindings(
            txt_pos=self._txt_pos,
            txt_vel=self._txt_vel,
            txt_amp=self._txt_amp,
            txt_temp=self._txt_temp,
            txt_guider_range_min=self._txt_guider_range_min,
            txt_guider_range_max=self._txt_guider_range_max,
            txt_guider_range_val=self._txt_guider_range_val,
            txt_guider_speed=self._txt_guider_speed,
            sld_vel_cmd=self._sld_vel_cmd,
            sld_limit_range=self._sld_limit_range,
        )

        self._b_banner = DenSiBannerBindings(
            left=self._txt_hdr_banner_left,
            right=self._txt_hdr_banner_right,
        )

        self._b_cut_markers = DenSiCutMarkersBindings(
            cut_time=self._txt_cut_time,
            cut_pos=self._txt_cut_pos,
            cut_vel=self._txt_cut_vel,
            posdiff=self._txt_posdiff,
        )

        self._wire_signals()

        log_missing_required_once(
            self.log,
            self._wcache,
            [
                (QComboBox, "cmb_axis"),
                (QLineEdit, "txt_tick"),
                (QLineEdit, "txtHdrBannerLeft"),
                (QLineEdit, "txtHdrBannerRight"),
            ],
            context="den_si:required",
        )
        log_missing_optional_once(
            self.log,
            self._wcache,
            [(QWidget, "dotHdrOnline")],
            context="den_si:hdr",
        )
        log_missing_optional_once(
            self.log,
            self._wcache,
            [
                (QLineEdit, "txt_tick"),
                (QLineEdit, "txt_pos"),
                (QLineEdit, "txt_vel"),
                (QLineEdit, "txt_amp"),
                (QLineEdit, "txt_temp"),
            ],
            context="den_si:readouts",
        )

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def seed_params_from_ui(self) -> dict[str, float]:
        params: dict[str, float] = {}
        for _grp, mapping in _PARAM_WIDGETS.items():
            for key, obj_name in mapping.items():
                le = self._find_line_edit(obj_name)
                if le is None:
                    continue
                try:
                    params[key] = float(le.text().strip() or "0")
                except ValueError:
                    continue
        return params

    def lock_param_ui_device_side(self) -> None:
        btn_names = [
            "btnPosEdit", "btnPosWrite", "btnPosCancel",
            "btnVelEdit", "btnVelWrite", "btnVelCancel",
            "btnFilterEdit", "btnFilterWrite", "btnFilterCancel",
            "btnGuiderEdit", "btnGuiderWrite", "btnGuiderCancel",
        ]
        for name in btn_names:
            b = self._wcache.button(name)
            if b is not None:
                set_enabled(b, False)

        for _grp, mapping in _PARAM_WIDGETS.items():
            for _key, wname in mapping.items():
                le = self._find_line_edit(wname)
                if le is None:
                    continue
                set_state_property(le, 'true', prop='paramField')
                set_enabled(le, False)

    def init_fixed_axis(self) -> None:
        if self._cmb_axis is None:
            return
        label = self.axis_ids[0] if self.axis_ids else "?"
        try:
            was = self._cmb_axis.blockSignals(True)
            self._cmb_axis.clear()
            self._cmb_axis.addItems([label])
            self._cmb_axis.setCurrentText(label)
            set_enabled(self._cmb_axis, False)
            self._cmb_axis.blockSignals(was)
        except Exception:
            pass

    def init_estop_checkboxes(self, *, estop_word: int) -> None:
        def _get_cb(obj_name: str) -> QCheckBox | None:
            try:
                return self._wcache.checkbox(obj_name)
            except Exception:
                w = self.win.findChild(QCheckBox, obj_name)
                return w if isinstance(w, QCheckBox) else None

        self._estop_cb_bindings = discover_densi_estop_checkboxes(get_checkbox=_get_cb)
        init_densi_estop_checkboxes(
            bindings=self._estop_cb_bindings,
            estop_word=int(estop_word),
            set_checked=lambda cb, v: set_checked(cb, v, block_signals=True),
            set_enabled=lambda cb, en: set_enabled(cb, en),
            readonly_keys={"reset_able"},
        )
        wire_densi_estop_checkboxes(bindings=self._estop_cb_bindings, on_toggled=self._on_estop_checkbox_toggled)

    def reset_ui_startup(self) -> None:
        if self._txt_tick is not None:
            set_text(self._txt_tick, "--")

        # DenSi role must not expose/enable ReSync (HiP owns workflow)
        if self._btn_diag_resync is not None:
            set_enabled(self._btn_diag_resync, False)

        # Disable operator-only buttons
        for name in ("btn_reset", "btnRecover"):
            b = self.win.findChild(QPushButton, name)
            if b is not None:
                set_enabled(b, False)

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------

    def read_inputs(self) -> DensiInputs:
        ui = self._ui_actions
        self._ui_actions = DensiUiInputs()
        return DensiInputs(frames=[], now_ns=0, ui=ui)

    # ------------------------------------------------------------------
    # Apply VM
    # ------------------------------------------------------------------

    def apply(self, vm: DensiViewModel) -> None:
        apply_densi_header_online_vm(vm.header_online, set_dot=self._set_dot)
        apply_densi_banner_vm(vm.banner, self._b_banner)
        apply_densi_estop_dots_vm(vm.estop_dots, set_dot=self._set_dot)
        apply_densi_readouts_vm(vm.readouts, self._b_readouts)
        apply_densi_cut_markers_vm(vm.cut_markers, self._b_cut_markers)
        apply_densi_lifetick_vm(vm.lifetick, txt_tick=self._txt_tick)

        if vm.refresh_checkboxes:
            if self._estop_cb_bindings is not None:
                sync_densi_estop_checkboxes(
                    bindings=self._estop_cb_bindings,
                    estop_word=int(vm.estop_word),
                    set_checked=lambda cb, v: set_checked(cb, v, block_signals=True),
                )
            else:
                bits = decode_estop_word(int(vm.estop_word))
                for spec in iter_specs():
                    if not spec.checkbox:
                        continue
                    cb = self.win.findChild(QCheckBox, spec.checkbox)
                    if cb is None:
                        continue
                    set_checked(cb, bool(bits.get(spec.key, False)), block_signals=True)

        if vm.applied_param_values:
            apply_param_values_to_line_edits(
                vm.applied_param_values,
                _PARAM_WIDGETS,
                self._find_line_edit,
                freeze_group="",
                skip_focused=True,
                block_signals=True,
            )

            limits_vm = compute_densi_limits_vm(values=vm.applied_param_values, limit_widgets=_LIMIT_WIDGETS)
            apply_densi_limits_vm(limits_vm, find_line_edit=self._find_line_edit)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        if self._btn_es_start is not None:
            self._btn_es_start.clicked.connect(self._on_es_start_clicked)
        if self._btn_estop_all_set is not None:
            self._btn_estop_all_set.clicked.connect(self._on_estop_all_set_clicked)
        if self._btn_estop_all_clear is not None:
            self._btn_estop_all_clear.clicked.connect(self._on_estop_all_clear_clicked)
        if self._btn_diag_resync is not None:
            self._btn_diag_resync.clicked.connect(self._on_diag_resync_clicked)

    def _on_es_start_clicked(self) -> None:
        self._ui_actions.es_start_clicked = True

    def _on_estop_all_set_clicked(self) -> None:
        self._ui_actions.estop_all_set_clicked = True

    def _on_estop_all_clear_clicked(self) -> None:
        self._ui_actions.estop_all_clear_clicked = True

    def _on_diag_resync_clicked(self) -> None:
        self._ui_actions.diag_resync_clicked = True

    def _on_estop_checkbox_toggled(self, key: str, checked: bool) -> None:
        self._ui_actions.estop_bit_toggles.append(DensiEstopToggle(key=str(key), checked=bool(checked)))

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

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
