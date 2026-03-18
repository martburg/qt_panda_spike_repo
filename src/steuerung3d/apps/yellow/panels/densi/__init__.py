"""DenSi panel view-models and render helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..._lazy_exports import resolve_lazy_export

__all__ = [
    "DenSiBannerVM",
    "DenSiCutMarkersVM",
    "CutMarkerEffects",
    "DenSiEstopDotsVM",
    "DenSiHeaderOnlineVM",
    "DenSiLifeTickVM",
    "DenSiLimitsVM",
    "DenSiReadoutsVM",
    "compute_densi_banner_vm",
    "compute_densi_cut_markers_vm",
    "compute_densi_estop_dots_vm",
    "compute_densi_header_online_vm",
    "compute_densi_lifetick_vm",
    "compute_densi_limits_vm",
    "compute_densi_readouts_vm",
]

if TYPE_CHECKING:  # pragma: no cover
    from .densi_banner_vm import DenSiBannerVM, compute_densi_banner_vm
    from .densi_cut_markers_vm import (
        CutMarkerEffects,
        DenSiCutMarkersVM,
        compute_densi_cut_markers_vm,
    )
    from .densi_estop_dots_vm import DenSiEstopDotsVM, compute_densi_estop_dots_vm
    from .densi_header_online_vm import DenSiHeaderOnlineVM, compute_densi_header_online_vm
    from .densi_lifetick_vm import DenSiLifeTickVM, compute_densi_lifetick_vm
    from .densi_limits_vm import DenSiLimitsVM, compute_densi_limits_vm
    from .densi_readouts_vm import DenSiReadoutsVM, compute_densi_readouts_vm

_EXPORTS = {
    "DenSiBannerVM": ("steuerung3d.apps.yellow.panels.densi.densi_banner_vm", "DenSiBannerVM"),
    "compute_densi_banner_vm": (
        "steuerung3d.apps.yellow.panels.densi.densi_banner_vm",
        "compute_densi_banner_vm",
    ),
    "DenSiCutMarkersVM": (
        "steuerung3d.apps.yellow.panels.densi.densi_cut_markers_vm",
        "DenSiCutMarkersVM",
    ),
    "CutMarkerEffects": (
        "steuerung3d.apps.yellow.panels.densi.densi_cut_markers_vm",
        "CutMarkerEffects",
    ),
    "compute_densi_cut_markers_vm": (
        "steuerung3d.apps.yellow.panels.densi.densi_cut_markers_vm",
        "compute_densi_cut_markers_vm",
    ),
    "DenSiEstopDotsVM": (
        "steuerung3d.apps.yellow.panels.densi.densi_estop_dots_vm",
        "DenSiEstopDotsVM",
    ),
    "compute_densi_estop_dots_vm": (
        "steuerung3d.apps.yellow.panels.densi.densi_estop_dots_vm",
        "compute_densi_estop_dots_vm",
    ),
    "DenSiHeaderOnlineVM": (
        "steuerung3d.apps.yellow.panels.densi.densi_header_online_vm",
        "DenSiHeaderOnlineVM",
    ),
    "compute_densi_header_online_vm": (
        "steuerung3d.apps.yellow.panels.densi.densi_header_online_vm",
        "compute_densi_header_online_vm",
    ),
    "DenSiLifeTickVM": (
        "steuerung3d.apps.yellow.panels.densi.densi_lifetick_vm",
        "DenSiLifeTickVM",
    ),
    "compute_densi_lifetick_vm": (
        "steuerung3d.apps.yellow.panels.densi.densi_lifetick_vm",
        "compute_densi_lifetick_vm",
    ),
    "DenSiLimitsVM": ("steuerung3d.apps.yellow.panels.densi.densi_limits_vm", "DenSiLimitsVM"),
    "compute_densi_limits_vm": (
        "steuerung3d.apps.yellow.panels.densi.densi_limits_vm",
        "compute_densi_limits_vm",
    ),
    "DenSiReadoutsVM": (
        "steuerung3d.apps.yellow.panels.densi.densi_readouts_vm",
        "DenSiReadoutsVM",
    ),
    "compute_densi_readouts_vm": (
        "steuerung3d.apps.yellow.panels.densi.densi_readouts_vm",
        "compute_densi_readouts_vm",
    ),
}


def __getattr__(name: str) -> Any:
    return resolve_lazy_export(name, _EXPORTS)
