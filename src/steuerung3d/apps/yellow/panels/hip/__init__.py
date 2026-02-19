"""HiP panel view-models and render helpers."""

from __future__ import annotations

__all__ = [
	"HipBannerState",
	"HipEstopState",
	"HipHeaderDots",
	"compute_hip_banner_vm",
	"compute_hip_estop_vm",
	"compute_hip_header_dots_vm",
]


def __getattr__(name: str):
	if name in ("compute_hip_banner_vm",):
		from .hip_banner_vm import compute_hip_banner_vm  # type: ignore

		return locals()[name]
	if name in ("compute_hip_estop_vm",):
		from .hip_estop_vm import compute_hip_estop_vm  # type: ignore

		return locals()[name]
	if name in ("compute_hip_header_dots_vm",):
		from .hip_header_dots_vm import compute_hip_header_dots_vm  # type: ignore

		return locals()[name]
	if name in ("HipBannerState", "HipEstopState", "HipHeaderDots"):
		from ...engines.hip.viewmodel import HipBannerState, HipEstopState, HipHeaderDots  # type: ignore

		return locals()[name]
	raise AttributeError(name)
