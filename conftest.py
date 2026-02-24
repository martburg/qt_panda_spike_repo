"""Pytest helper.

This repo uses a src/ layout. When running tests without installing the package,
we add ./src to sys.path so `import steuerung3d` works.

If you prefer, you can instead do: `python -m pip install -e .`
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))
import importlib.util
import os

import pytest


def _has_pyside6() -> bool:
    return importlib.util.find_spec("PySide6") is not None


def _has_transitions() -> bool:
    return importlib.util.find_spec("transitions") is not None


def pytest_runtest_setup(item: pytest.Item) -> None:
    if "ui" in item.keywords and not _has_pyside6():
        pytest.skip("PySide6 not installed; skipping UI test")

    # Optional dependency gate: only run when explicitly opted-in.
    if "requires_transitions" in item.keywords:
        if os.environ.get("RUN_TRANSITIONS_TESTS", "0") != "1":
            pytest.skip("transitions tests are opt-in; set RUN_TRANSITIONS_TESTS=1")
        if not _has_transitions():
            pytest.skip("transitions not installed")
