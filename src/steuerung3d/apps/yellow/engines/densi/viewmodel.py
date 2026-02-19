"""DenSi view-model types (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass

from ...panels.densi_banner_vm import DenSiBannerVM
from ...panels.densi_cut_markers_vm import DenSiCutMarkersVM
from ...panels.densi_estop_dots_vm import DenSiEstopDotsVM
from ...panels.densi_header_online_vm import DenSiHeaderOnlineVM
from ...panels.densi_lifetick_vm import DenSiLifeTickVM
from ...panels.densi_readouts_vm import DenSiReadoutsVM


@dataclass(frozen=True)
class DensiViewModel:
    header_online: DenSiHeaderOnlineVM
    banner: DenSiBannerVM
    estop_dots: DenSiEstopDotsVM
    readouts: DenSiReadoutsVM
    cut_markers: DenSiCutMarkersVM
    lifetick: DenSiLifeTickVM
    estop_word: int
    refresh_checkboxes: bool
    applied_param_values: dict[str, float]


def normalize_densi_view_model(vm: DensiViewModel) -> dict[str, object]:
    return {
        "header_online": str(vm.header_online.dot_state),
        "banner": str(vm.banner.estate),
        "estop_word": int(vm.estop_word),
        "readouts": {
            "pos": str(vm.readouts.pos_text),
            "vel": str(vm.readouts.vel_text),
            "amp": str(vm.readouts.amp_text),
            "temp": str(vm.readouts.temp_text),
        },
        "lifetick": str(vm.lifetick.text),
    }
