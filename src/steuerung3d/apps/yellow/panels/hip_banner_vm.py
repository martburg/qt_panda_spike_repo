"""HiP banner view-model (Qt-free)."""

from __future__ import annotations

from ..domain.ui_banner import BANNER_COLORS, derive_banner_estate_from_word
from ..engines.hip.viewmodel import HipBannerState


def compute_hip_banner_vm(*, estop_word: int, within_brake_grace: bool) -> HipBannerState:
    estate = derive_banner_estate_from_word(
        int(estop_word),
        within_brake_grace=(lambda: bool(within_brake_grace)),
    )
    bg, fg = BANNER_COLORS.get(estate, ("#F9E547", "#000000"))
    return HipBannerState(
        estate=str(estate),
        bg=str(bg),
        fg=str(fg),
        left_text=str(estate),
        right_text=str(estate),
    )
