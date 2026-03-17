"""DenSi panel view-models and render helpers."""

from __future__ import annotations

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


def __getattr__(name: str):
    return resolve_lazy_export(name, _EXPORTS)
