"""DenSi readouts renderer (Qt-only).

This module applies :class:`~steuerung3d.apps.yellow.panels.densi_readouts_vm.DenSiReadoutsVM`
to a set of Qt widgets.

Keep this module dumb: no decisions, no policy, just applying already-decided
values with minimal churn.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ..controllers.ui_update import set_text, update_slider

from .densi_readouts_vm import DenSiReadoutsVM

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QAbstractSlider, QLineEdit


@dataclass(frozen=True)
class DenSiReadoutsBindings:
    txt_pos: "QLineEdit | None" = None
    txt_vel: "QLineEdit | None" = None
    txt_amp: "QLineEdit | None" = None
    txt_temp: "QLineEdit | None" = None

    txt_guider_range_min: "QLineEdit | None" = None
    txt_guider_range_max: "QLineEdit | None" = None
    txt_guider_range_val: "QLineEdit | None" = None
    txt_guider_speed: "QLineEdit | None" = None

    sld_vel_cmd: "QAbstractSlider | None" = None
    sld_limit_range: "QAbstractSlider | None" = None


def apply_densi_readouts_vm(vm: DenSiReadoutsVM, b: DenSiReadoutsBindings) -> None:
    # Primary live readouts
    set_text(b.txt_pos, vm.pos_text)
    set_text(b.txt_vel, vm.vel_text)
    set_text(b.txt_amp, vm.amp_text)
    set_text(b.txt_temp, vm.temp_text)

    # Guider readouts
    set_text(b.txt_guider_range_min, vm.guider_min_text)
    set_text(b.txt_guider_range_max, vm.guider_max_text)
    set_text(b.txt_guider_range_val, vm.guider_val_text)
    set_text(b.txt_guider_speed, vm.guider_speed_text)

    # Slider indicators
    update_slider(
        b.sld_vel_cmd,
        minimum=vm.vel_cmd_min,
        maximum=vm.vel_cmd_max,
        value=vm.vel_cmd_val,
        block_signals=True,
    )
    update_slider(
        b.sld_limit_range,
        minimum=vm.limit_min,
        maximum=vm.limit_max,
        value=vm.limit_val,
        block_signals=True,
    )
