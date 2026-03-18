"""Qt-only drive status rendering helpers for Hip panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QLineEdit

from ...qtutil.ui_update import set_text


@dataclass(frozen=True)
class HipDriveStatusBindings:
    txt_main_amp_status: QLineEdit | None
    txt_slave_amp_status: QLineEdit | None


def apply_hip_drive_status(bindings: HipDriveStatusBindings, vm_or_fragment: Any) -> None:
    ds = getattr(vm_or_fragment, "drive_status", vm_or_fragment)
    if ds is None:
        return
    if bindings.txt_main_amp_status is not None:
        set_text(bindings.txt_main_amp_status, str(ds.main_text))
    if bindings.txt_slave_amp_status is not None:
        set_text(bindings.txt_slave_amp_status, str(ds.slave_text))
