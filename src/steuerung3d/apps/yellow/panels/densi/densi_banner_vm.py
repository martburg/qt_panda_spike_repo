"""DenSi banner (ESTOP/IDLE/ARMED/READY) view-model (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.ui_banner import BANNER_COLORS, derive_banner_estate_from_word


@dataclass(frozen=True)
class DenSiBannerVM:
    estate: str
    bg: str
    fg: str


def compute_densi_banner_vm(
    *,
    estop_word: int,
    within_brake_grace: bool,
) -> DenSiBannerVM:
    estate = derive_banner_estate_from_word(
        int(estop_word),
        within_brake_grace=(lambda: bool(within_brake_grace)),
    )
    bg, fg = BANNER_COLORS.get(estate, ("#F9E547", "#000000"))
    return DenSiBannerVM(estate=str(estate), bg=str(bg), fg=str(fg))
