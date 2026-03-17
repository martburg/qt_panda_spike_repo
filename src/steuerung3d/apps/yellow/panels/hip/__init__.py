"""HiP panel view-models and render helpers."""

from __future__ import annotations

from ..._lazy_exports import resolve_lazy_export

__all__ = [
    "HipBannerState",
    "HipEstopState",
    "HipHeaderDots",
    "compute_hip_banner_vm",
    "compute_hip_estop_vm",
    "compute_hip_header_dots_vm",
]

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


def __getattr__(name: str):
    return resolve_lazy_export(name, _EXPORTS)
