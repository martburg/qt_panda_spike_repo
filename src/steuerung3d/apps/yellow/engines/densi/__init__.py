"""DenSi engine modules."""

from __future__ import annotations

__all__ = [
    "DenSiEngine",
    "DenSiTickResult",
    "DensiInputs",
    "DensiUiInputs",
    "DensiEstopToggle",
    "EStopState",
    "L0Top",
    "L0Sub",
    "DensiViewModel",
    "normalize_densi_view_model",
]


def __getattr__(name: str):
    if name in __all__:
        from .engine import DenSiEngine, DenSiTickResult  # type: ignore
        from .inputs import DensiEstopToggle, DensiInputs, DensiUiInputs  # type: ignore
        from .types import EStopState, L0Sub, L0Top  # type: ignore
        from .viewmodel import DensiViewModel, normalize_densi_view_model  # type: ignore

        return locals()[name]
    raise AttributeError(name)
