"""DenSi engine modules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..._lazy_exports import resolve_lazy_export

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

if TYPE_CHECKING:  # pragma: no cover
    from .engine import DenSiEngine
    from .engine_types import DenSiTickResult
    from .inputs import DensiEstopToggle, DensiInputs, DensiUiInputs
    from .types import EStopState, L0Sub, L0Top
    from .viewmodel import DensiViewModel, normalize_densi_view_model

_EXPORTS = {
    "DenSiEngine": ("steuerung3d.apps.yellow.engines.densi.engine", "DenSiEngine"),
    "DenSiTickResult": ("steuerung3d.apps.yellow.engines.densi.engine_types", "DenSiTickResult"),
    "DensiInputs": ("steuerung3d.apps.yellow.engines.densi.inputs", "DensiInputs"),
    "DensiUiInputs": ("steuerung3d.apps.yellow.engines.densi.inputs", "DensiUiInputs"),
    "DensiEstopToggle": ("steuerung3d.apps.yellow.engines.densi.inputs", "DensiEstopToggle"),
    "EStopState": ("steuerung3d.apps.yellow.engines.densi.types", "EStopState"),
    "L0Top": ("steuerung3d.apps.yellow.engines.densi.types", "L0Top"),
    "L0Sub": ("steuerung3d.apps.yellow.engines.densi.types", "L0Sub"),
    "DensiViewModel": ("steuerung3d.apps.yellow.engines.densi.viewmodel", "DensiViewModel"),
    "normalize_densi_view_model": (
        "steuerung3d.apps.yellow.engines.densi.viewmodel",
        "normalize_densi_view_model",
    ),
}


def __getattr__(name: str) -> Any:
    return resolve_lazy_export(name, _EXPORTS)
