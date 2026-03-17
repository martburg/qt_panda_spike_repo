"""Qt-free engines for Yellow apps.

This package intentionally keeps deterministic device semantics (DenSi) out of
Qt controllers. Controllers should remain wiring + rendering only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._lazy_exports import resolve_lazy_export
from .densi.types import EStopState, L0Sub, L0Top

if TYPE_CHECKING:
    from .densi.engine import DenSiEngine
    from .densi.engine_types import DenSiTickResult
    from .hip.engine import (
        HipAttachInputs,
        HipAttachState,
        HipBannerInputs,
        HipEngine,
        HipParamCommitDialog,
        HipState,
        HipStepInputs,
        HipStepResult,
        HipViewModel,
    )

__all__ = [
    "DenSiEngine",
    "DenSiTickResult",
    "EStopState",
    "L0Top",
    "L0Sub",
    "HipEngine",
    "HipAttachInputs",
    "HipAttachState",
    "HipBannerInputs",
    "HipParamCommitDialog",
    "HipState",
    "HipViewModel",
    "HipStepInputs",
    "HipStepResult",
]

_EXPORTS = {
    "DenSiEngine": ("steuerung3d.apps.yellow.engines.densi.engine", "DenSiEngine"),
    "DenSiTickResult": ("steuerung3d.apps.yellow.engines.densi.engine_types", "DenSiTickResult"),
    "HipEngine": ("steuerung3d.apps.yellow.engines.hip.engine", "HipEngine"),
    "HipAttachInputs": ("steuerung3d.apps.yellow.engines.hip.engine", "HipAttachInputs"),
    "HipAttachState": ("steuerung3d.apps.yellow.engines.hip.engine", "HipAttachState"),
    "HipBannerInputs": ("steuerung3d.apps.yellow.engines.hip.engine", "HipBannerInputs"),
    "HipParamCommitDialog": ("steuerung3d.apps.yellow.engines.hip.engine", "HipParamCommitDialog"),
    "HipState": ("steuerung3d.apps.yellow.engines.hip.engine", "HipState"),
    "HipViewModel": ("steuerung3d.apps.yellow.engines.hip.engine", "HipViewModel"),
    "HipStepInputs": ("steuerung3d.apps.yellow.engines.hip.engine", "HipStepInputs"),
    "HipStepResult": ("steuerung3d.apps.yellow.engines.hip.engine", "HipStepResult"),
}


def __getattr__(name: str):
    if name in {"EStopState", "L0Top", "L0Sub"}:
        return globals()[name]
    return resolve_lazy_export(name, _EXPORTS)
