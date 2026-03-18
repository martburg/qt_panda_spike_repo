"""HiP panel view-models and render helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..._lazy_exports import resolve_lazy_export

__all__ = [
    "HipBannerState",
    "HipEstopState",
    "HipHeaderDots",
    "compute_hip_banner_vm",
    "compute_hip_estop_vm",
    "compute_hip_header_dots_vm",
]

if TYPE_CHECKING:  # pragma: no cover
    from ...engines.hip.viewmodel import HipBannerState, HipEstopState, HipHeaderDots
    from .hip_banner_vm import compute_hip_banner_vm
    from .hip_estop_vm import compute_hip_estop_vm
    from .hip_header_dots_vm import compute_hip_header_dots_vm

_EXPORTS = {
    "compute_hip_banner_vm": (
        "steuerung3d.apps.yellow.panels.hip.hip_banner_vm",
        "compute_hip_banner_vm",
    ),
    "compute_hip_estop_vm": (
        "steuerung3d.apps.yellow.panels.hip.hip_estop_vm",
        "compute_hip_estop_vm",
    ),
    "compute_hip_header_dots_vm": (
        "steuerung3d.apps.yellow.panels.hip.hip_header_dots_vm",
        "compute_hip_header_dots_vm",
    ),
    "HipBannerState": ("steuerung3d.apps.yellow.engines.hip.viewmodel", "HipBannerState"),
    "HipEstopState": ("steuerung3d.apps.yellow.engines.hip.viewmodel", "HipEstopState"),
    "HipHeaderDots": ("steuerung3d.apps.yellow.engines.hip.viewmodel", "HipHeaderDots"),
}


def __getattr__(name: str) -> Any:
    return resolve_lazy_export(name, _EXPORTS)
