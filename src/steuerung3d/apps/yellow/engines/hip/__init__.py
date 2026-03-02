"""HiP engine modules (split by refactor)."""

from __future__ import annotations

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


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)

    from .engine import (  # type: ignore
        HipAttachInputs,
        HipAttachState,
        HipBannerInputs,
        HipEngine,
        HipParamAction,
        HipParamCommitDialog,
        HipState,
        HipStepInputs,
        HipStepResult,
        HipUiInputs,
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
    if name == "HipParamAction":
        return HipParamAction
    if name == "HipParamCommitDialog":
        return HipParamCommitDialog
    if name == "HipState":
        return HipState
    if name == "HipUiInputs":
        return HipUiInputs
    if name == "HipViewModel":
        return HipViewModel
    if name == "HipStepInputs":
        return HipStepInputs
    if name == "HipStepResult":
        return HipStepResult

    # Defensive fallback (should not be reachable)
    raise AttributeError(name)
