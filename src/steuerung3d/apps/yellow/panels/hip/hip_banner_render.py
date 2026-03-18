"""Qt-only banner rendering helpers for Hip panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from PySide6.QtWidgets import QLineEdit

from ...domain.ui_banner import BANNER_COLORS
from ...qtutil.ui_update import set_text


@dataclass(frozen=True)
class HipBannerBindings:
    txt_hdr_banner_left: Optional[QLineEdit]
    txt_hdr_banner_right: Optional[QLineEdit]


def apply_hip_banner(bindings: HipBannerBindings, banner_or_vm: Any) -> None:
    banner = getattr(banner_or_vm, "banner", banner_or_vm)
    if banner is None:
        return

    bg, fg = BANNER_COLORS.get(str(banner.estate), ("#F9E547", "#000000"))
    for w in (bindings.txt_hdr_banner_left, bindings.txt_hdr_banner_right):
        if w is None:
            continue
        set_text(w, str(banner.estate))
        w.setStyleSheet(f"background-color: {bg}; color: {fg}; font-weight: 700;")
