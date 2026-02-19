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

		return locals()[name]
	if name in ("DenSiCutMarkersVM", "CutMarkerEffects", "compute_densi_cut_markers_vm"):
		from .densi_cut_markers_vm import (  # type: ignore
			DenSiCutMarkersVM,
			CutMarkerEffects,
			compute_densi_cut_markers_vm,
		)

		return locals()[name]
	if name in ("DenSiEstopDotsVM", "compute_densi_estop_dots_vm"):
		from .densi_estop_dots_vm import DenSiEstopDotsVM, compute_densi_estop_dots_vm  # type: ignore

		return locals()[name]
	if name in ("DenSiHeaderOnlineVM", "compute_densi_header_online_vm"):
		from .densi_header_online_vm import DenSiHeaderOnlineVM, compute_densi_header_online_vm  # type: ignore

		return locals()[name]
	if name in ("DenSiLifeTickVM", "compute_densi_lifetick_vm"):
		from .densi_lifetick_vm import DenSiLifeTickVM, compute_densi_lifetick_vm  # type: ignore

		return locals()[name]
	if name in ("DenSiLimitsVM", "compute_densi_limits_vm"):
		from .densi_limits_vm import DenSiLimitsVM, compute_densi_limits_vm  # type: ignore

		return locals()[name]
	if name in ("DenSiReadoutsVM", "compute_densi_readouts_vm"):
		from .densi_readouts_vm import DenSiReadoutsVM, compute_densi_readouts_vm  # type: ignore

		return locals()[name]
	raise AttributeError(name)
