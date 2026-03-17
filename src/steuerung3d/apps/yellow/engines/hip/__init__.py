"""HiP engine modules (split by refactor)."""

from __future__ import annotations

from ..._lazy_exports import resolve_lazy_export

__all__ = [
    "HipEngine",
    "HipAttachInputs",
    "HipAttachState",
    "HipBannerInputs",
    "HipParamAction",
    "HipParamCommitDialog",
    "HipState",
    "HipUiInputs",
    "HipViewModel",
    "HipStepInputs",
    "HipStepResult",
]

_EXPORTS = {
    "HipEngine": ("steuerung3d.apps.yellow.engines.hip.engine", "HipEngine"),
    "HipAttachInputs": ("steuerung3d.apps.yellow.engines.hip.engine", "HipAttachInputs"),
    "HipAttachState": ("steuerung3d.apps.yellow.engines.hip.types", "HipAttachState"),
    "HipBannerInputs": ("steuerung3d.apps.yellow.engines.hip.engine", "HipBannerInputs"),
    "HipParamAction": ("steuerung3d.apps.yellow.engines.hip.engine", "HipParamAction"),
    "HipParamCommitDialog": ("steuerung3d.apps.yellow.engines.hip.types", "HipParamCommitDialog"),
    "HipState": ("steuerung3d.apps.yellow.engines.hip.engine", "HipState"),
    "HipUiInputs": ("steuerung3d.apps.yellow.engines.hip.engine", "HipUiInputs"),
    "HipViewModel": ("steuerung3d.apps.yellow.engines.hip.engine", "HipViewModel"),
    "HipStepInputs": ("steuerung3d.apps.yellow.engines.hip.engine", "HipStepInputs"),
    "HipStepResult": ("steuerung3d.apps.yellow.engines.hip.engine", "HipStepResult"),
}


def __getattr__(name: str):
    return resolve_lazy_export(name, _EXPORTS)
