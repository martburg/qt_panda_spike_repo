"""Qt-only header dots rendering helpers for Hip panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QWidget

from ...qtutil.ui_update import set_state_property


@dataclass(frozen=True)
class HipHeaderDotsBindings:
    dot_hdr_online: QWidget | None
    dot_hdr_ready: QWidget | None
    dot_hdr_fbt: QWidget | None
    dot_hdr_brake1: QWidget | None
    dot_hdr_brake2: QWidget | None


def _set_dot(widget: QWidget | None, state: object) -> None:
    if widget is None:
        return
    set_state_property(widget, state)


def apply_hip_header_dots(bindings: HipHeaderDotsBindings, vm_or_fragment: Any) -> None:
    header = getattr(vm_or_fragment, "header_dots", vm_or_fragment)
    if header is None:
        return
    _set_dot(bindings.dot_hdr_online, getattr(header, "online_state", None))
    _set_dot(bindings.dot_hdr_ready, getattr(header, "ready_state", None))
    _set_dot(bindings.dot_hdr_fbt, getattr(header, "fbt_state", None))
    _set_dot(bindings.dot_hdr_brake1, getattr(header, "brk1_state", None))
    _set_dot(bindings.dot_hdr_brake2, getattr(header, "brk2_state", None))
