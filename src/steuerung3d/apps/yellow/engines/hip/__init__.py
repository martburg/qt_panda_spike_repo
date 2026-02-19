"""HiP engine modules (split by refactor)."""

from __future__ import annotations

__all__ = [
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
	if name in __all__:
		from .engine import (  # type: ignore
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
