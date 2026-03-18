"""Qt-only slider rendering helpers for Hip panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QAbstractSlider

from ...qtutil.ui_update import update_slider


@dataclass(frozen=True)
class HipSlidersBindings:
    sld_vel_cmd: QAbstractSlider
    sld_limit_range: QAbstractSlider
    sld_guider_range: QAbstractSlider
    sld_guider_speed: QAbstractSlider


def apply_hip_sliders(bindings: HipSlidersBindings, vm: Any) -> None:
    ro = getattr(vm, "readouts", None)
    if ro is None:
        return

    update_slider(
        bindings.sld_vel_cmd,
        minimum=int(ro.vel_cmd_min),
        maximum=int(ro.vel_cmd_max),
        value=int(ro.vel_cmd_val),
    )
    update_slider(
        bindings.sld_limit_range,
        minimum=int(ro.limit_min),
        maximum=int(ro.limit_max),
        value=int(ro.limit_val),
    )
    update_slider(
        bindings.sld_guider_range,
        minimum=int(ro.guider_range_min),
        maximum=int(ro.guider_range_max),
        value=int(ro.guider_range_val),
    )
    update_slider(
        bindings.sld_guider_speed,
        minimum=int(ro.guider_speed_min),
        maximum=int(ro.guider_speed_max),
        value=int(ro.guider_speed_val),
    )
