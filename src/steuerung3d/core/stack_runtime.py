"""Run a stack profile as supervised subprocesses.

Public API wrapper.

This module intentionally re-exports the stable public surface from
:mod:`steuerung3d.core.stack_runtime_impl` so we can keep imports stable while
splitting implementation into smaller modules.
"""

from __future__ import annotations

from .stack_runtime_impl import StackRuntime, expand_processes

# Historically these were imported here and consumed by tests via this module.
from steuerung3d.ui.birdseye_format import (  # noqa: F401
    birdseye_multiline_default,
    build_frederik_panel_lines,
    format_birds_eye,
    tail_lines,
)

__all__ = [
    "StackRuntime",
    "expand_processes",
    "birdseye_multiline_default",
    "build_frederik_panel_lines",
    "format_birds_eye",
    "tail_lines",
]
