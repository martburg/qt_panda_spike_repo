"""HiP view-model helpers (compat shim)."""

from __future__ import annotations

from typing import Any, Iterable

from .engine import HipEngine, HipViewModel


def normalize_intents(intents: Iterable[object]) -> list[tuple[str, tuple[tuple[str, Any], ...]]]:
    return HipEngine.normalize_intents(intents)


def normalize_view_model(vm: HipViewModel) -> dict[str, Any]:
    return HipEngine.normalize_view_model(vm)


__all__ = [
    "HipEngine",
    "HipViewModel",
    "normalize_intents",
    "normalize_view_model",
]
