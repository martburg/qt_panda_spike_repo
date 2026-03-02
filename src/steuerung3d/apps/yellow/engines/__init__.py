"""Qt-free engines for Yellow apps.

This package intentionally keeps deterministic device semantics (DenSi) out of
Qt controllers. Controllers should remain wiring + rendering only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .densi.types import EStopState, L0Sub, L0Top

if TYPE_CHECKING:
    from .densi.engine import DenSiEngine, DenSiTickResult
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


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)

    if name in ("DenSiEngine", "DenSiTickResult"):
        from .densi.engine import DenSiEngine, DenSiTickResult  # type: ignore

        if name == "DenSiEngine":
            return DenSiEngine
        return DenSiTickResult

    if name in (
        "HipEngine",
        "HipAttachInputs",
        "HipAttachState",
        "HipBannerInputs",
        "HipParamCommitDialog",
        "HipState",
        "HipViewModel",
        "HipStepInputs",
        "HipStepResult",
    ):
        from .hip.engine import (  # type: ignore
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

        if name == "HipEngine":
            return HipEngine
        if name == "HipAttachInputs":
            return HipAttachInputs
        if name == "HipAttachState":
            return HipAttachState
        if name == "HipBannerInputs":
            return HipBannerInputs
        if name == "HipParamCommitDialog":
            return HipParamCommitDialog
        if name == "HipState":
            return HipState
        if name == "HipViewModel":
            return HipViewModel
        if name == "HipStepInputs":
            return HipStepInputs
        return HipStepResult

    # Defensive fallback (should not be reachable)
    raise AttributeError(name)