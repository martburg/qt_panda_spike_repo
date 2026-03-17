"""Helpers for package-level lazy exports in Yellow."""

from __future__ import annotations

from importlib import import_module
from typing import Mapping, TypeAlias

LazyExport: TypeAlias = tuple[str, str]
LazyExportMap: TypeAlias = Mapping[str, LazyExport]


def resolve_lazy_export(name: str, exports: LazyExportMap) -> object:
    """Resolve ``name`` from a ``name -> (module_path, attr_name)`` map."""
    try:
        module_path, attr_name = exports[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_path)
    return getattr(module, attr_name)
