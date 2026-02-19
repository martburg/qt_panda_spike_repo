"""Qt-only cut markers rendering helpers for Hip panels."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QLineEdit

from ...qtutil.ui_update import set_text


@dataclass(frozen=True)
class HipCutMarkersBindings:
    txt_cut_time: QLineEdit | None
    txt_cut_pos: QLineEdit | None
    txt_cut_vel: QLineEdit | None
    txt_posdiff: QLineEdit | None


def apply_hip_cut_markers(bindings: HipCutMarkersBindings, vm_or_fragment) -> None:
    cut = getattr(vm_or_fragment, "cut_markers", vm_or_fragment)
    if cut is None:
        return
    if bindings.txt_cut_time is not None:
        set_text(bindings.txt_cut_time, cut.cut_time_text)
    if bindings.txt_cut_pos is not None:
        set_text(bindings.txt_cut_pos, cut.cut_pos_text)
    if bindings.txt_cut_vel is not None:
        set_text(bindings.txt_cut_vel, cut.cut_vel_text)
    if bindings.txt_posdiff is not None:
        set_text(bindings.txt_posdiff, cut.posdiff_text)
