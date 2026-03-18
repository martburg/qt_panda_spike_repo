"""Qt-only readouts rendering helpers for Hip panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QLineEdit

from ...qtutil.ui_update import set_text


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


def apply_hip_readouts(bindings: HipReadoutsBindings, vm: Any) -> None:
    ro = getattr(vm, "readouts", None)
    if ro is None:
        return

    set_text(bindings.txt_pos, str(ro.pos_text))
    set_text(bindings.txt_vel, str(ro.vel_text))
    set_text(bindings.txt_amp, str(ro.amp_text))
    set_text(bindings.txt_temp, str(ro.temp_text))

    set_text(bindings.txt_guider_range_min, str(ro.guider_min_text))
    set_text(bindings.txt_guider_range_max, str(ro.guider_max_text))
    set_text(bindings.txt_guider_range_val, str(ro.guider_val_text))
    set_text(bindings.txt_guider_speed, str(ro.guider_speed_text))
