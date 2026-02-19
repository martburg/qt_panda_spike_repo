"""Qt-free engines for Yellow apps.

This package intentionally keeps deterministic device semantics (DenSi) out of
Qt controllers. Controllers should remain wiring + rendering only.
"""

from .densi.engine import DenSiEngine, DenSiTickResult
from .densi.types import EStopState, L0Top, L0Sub

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


def __getattr__(name: str):
    if name in {
        "HipEngine",
        "HipAttachInputs",
        "HipAttachState",
        "HipBannerInputs",
        "HipParamCommitDialog",
        "HipState",
        "HipViewModel",
        "HipStepInputs",
        "HipStepResult",
    }:
        from .hip.engine import (  # type: ignore
            HipEngine,
            HipAttachInputs,
            HipAttachState,
            HipBannerInputs,
            HipParamCommitDialog,
            HipState,
            HipViewModel,
            HipStepInputs,
            HipStepResult,
        )

        return locals()[name]
    raise AttributeError(name)
