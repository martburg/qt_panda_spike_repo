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
    if name not in __all__:
        raise AttributeError(name)

    from .engine import DenSiEngine  # type: ignore
    from .engine_types import DenSiTickResult  # type: ignore
    from .inputs import DensiEstopToggle, DensiInputs, DensiUiInputs  # type: ignore
    from .types import EStopState, L0Sub, L0Top  # type: ignore
    from .viewmodel import DensiViewModel, normalize_densi_view_model  # type: ignore

    if name == "DenSiEngine":
        return DenSiEngine
    if name == "DenSiTickResult":
        return DenSiTickResult
    if name == "DensiInputs":
        return DensiInputs
    if name == "DensiUiInputs":
        return DensiUiInputs
    if name == "DensiEstopToggle":
        return DensiEstopToggle
    if name == "EStopState":
        return EStopState
    if name == "L0Top":
        return L0Top
    if name == "L0Sub":
        return L0Sub
    if name == "DensiViewModel":
        return DensiViewModel
    if name == "normalize_densi_view_model":
        return normalize_densi_view_model

    # Defensive fallback (should not be reachable)
    raise AttributeError(name)
