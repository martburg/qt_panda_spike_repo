"""DenSi panel view-models and render helpers."""

from __future__ import annotations

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


def __getattr__(name: str):
    if name in ("DenSiBannerVM", "compute_densi_banner_vm"):
        from .densi_banner_vm import DenSiBannerVM, compute_densi_banner_vm  # type: ignore

        if name == "DenSiBannerVM":
            return DenSiBannerVM
        return compute_densi_banner_vm

    if name in ("DenSiCutMarkersVM", "CutMarkerEffects", "compute_densi_cut_markers_vm"):
        from .densi_cut_markers_vm import (  # type: ignore
            CutMarkerEffects,
            DenSiCutMarkersVM,
            compute_densi_cut_markers_vm,
        )

        if name == "DenSiCutMarkersVM":
            return DenSiCutMarkersVM
        if name == "CutMarkerEffects":
            return CutMarkerEffects
        return compute_densi_cut_markers_vm

    if name in ("DenSiEstopDotsVM", "compute_densi_estop_dots_vm"):
        from .densi_estop_dots_vm import (  # type: ignore
            DenSiEstopDotsVM,
            compute_densi_estop_dots_vm,
        )

        if name == "DenSiEstopDotsVM":
            return DenSiEstopDotsVM
        return compute_densi_estop_dots_vm

    if name in ("DenSiHeaderOnlineVM", "compute_densi_header_online_vm"):
        from .densi_header_online_vm import (  # type: ignore
            DenSiHeaderOnlineVM,
            compute_densi_header_online_vm,
        )

        if name == "DenSiHeaderOnlineVM":
            return DenSiHeaderOnlineVM
        return compute_densi_header_online_vm

    if name in ("DenSiLifeTickVM", "compute_densi_lifetick_vm"):
        from .densi_lifetick_vm import DenSiLifeTickVM, compute_densi_lifetick_vm  # type: ignore

        if name == "DenSiLifeTickVM":
            return DenSiLifeTickVM
        return compute_densi_lifetick_vm

    if name in ("DenSiLimitsVM", "compute_densi_limits_vm"):
        from .densi_limits_vm import DenSiLimitsVM, compute_densi_limits_vm  # type: ignore

        if name == "DenSiLimitsVM":
            return DenSiLimitsVM
        return compute_densi_limits_vm

    if name in ("DenSiReadoutsVM", "compute_densi_readouts_vm"):
        from .densi_readouts_vm import DenSiReadoutsVM, compute_densi_readouts_vm  # type: ignore

        if name == "DenSiReadoutsVM":
            return DenSiReadoutsVM
        return compute_densi_readouts_vm

    raise AttributeError(name)