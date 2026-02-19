"""Qt-only renderer for DenSi cut markers."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QLineEdit

from ..qtutil.ui_update import set_text
from .densi_cut_markers_vm import DenSiCutMarkersVM


@dataclass
class DenSiCutMarkersBindings:
    cut_time: QLineEdit | None
    cut_pos: QLineEdit | None
    cut_vel: QLineEdit | None
    posdiff: QLineEdit | None


def apply_densi_cut_markers_vm(vm: DenSiCutMarkersVM, b: DenSiCutMarkersBindings) -> None:
    if b.cut_time is not None:
        set_text(b.cut_time, vm.cut_time_text)
    if b.cut_pos is not None:
        set_text(b.cut_pos, vm.cut_pos_text)
    if b.cut_vel is not None:
        set_text(b.cut_vel, vm.cut_vel_text)
    if b.posdiff is not None:
        set_text(b.posdiff, vm.posdiff_text)
