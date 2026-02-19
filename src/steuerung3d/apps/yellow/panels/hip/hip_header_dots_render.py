"""Qt-only header dots rendering helpers for Hip panels."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from ...qtutil.ui_update import set_state_property


@dataclass(frozen=True)
class HipHeaderDotsBindings:
    dot_hdr_online: QWidget | None
    dot_hdr_ready: QWidget | None
    dot_hdr_fbt: QWidget | None
    dot_hdr_brake1: QWidget | None
    dot_hdr_brake2: QWidget | None


def _set_dot(widget: QWidget | None, state) -> None:
    if widget is None:
        return
    set_state_property(widget, state)


def apply_hip_header_dots(bindings: HipHeaderDotsBindings, vm_or_fragment) -> None:
    header = getattr(vm_or_fragment, "header_dots", vm_or_fragment)
    if header is None:
        return
    _set_dot(bindings.dot_hdr_online, header.online_state)
    _set_dot(bindings.dot_hdr_ready, header.ready_state)
    _set_dot(bindings.dot_hdr_fbt, header.fbt_state)
    _set_dot(bindings.dot_hdr_brake1, header.brk1_state)
    _set_dot(bindings.dot_hdr_brake2, header.brk2_state)
