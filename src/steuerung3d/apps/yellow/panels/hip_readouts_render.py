"""Qt-only readouts rendering helpers for Hip panels."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QLineEdit

from ..qtutil.ui_update import set_text


@dataclass(frozen=True)
class HipReadoutsBindings:
    txt_pos: QLineEdit
    txt_vel: QLineEdit
    txt_amp: QLineEdit
    txt_temp: QLineEdit
    txt_guider_range_min: QLineEdit
    txt_guider_range_max: QLineEdit
    txt_guider_range_val: QLineEdit
    txt_guider_speed: QLineEdit


def apply_hip_readouts(bindings: HipReadoutsBindings, vm) -> None:
    ro = getattr(vm, "readouts", None)
    if ro is None:
        return

    set_text(bindings.txt_pos, ro.pos_text)
    set_text(bindings.txt_vel, ro.vel_text)
    set_text(bindings.txt_amp, ro.amp_text)
    set_text(bindings.txt_temp, ro.temp_text)

    set_text(bindings.txt_guider_range_min, ro.guider_min_text)
    set_text(bindings.txt_guider_range_max, ro.guider_max_text)
    set_text(bindings.txt_guider_range_val, ro.guider_val_text)
    set_text(bindings.txt_guider_speed, ro.guider_speed_text)

