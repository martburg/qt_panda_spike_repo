import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, cast

import pytest
from _pytest.config import Config
from _pytest.nodes import Item

# Ensure `src/` layout works when running `pytest` directly (no editable install).
# This keeps test collection robust in fresh environments and CI.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def pytest_configure(config: Config) -> None:
    config.addinivalue_line("markers", "integration: integration-style UDP roundtrip tests")
    config.addinivalue_line(
        "markers",
        "requires_module(name): skip test if the given Python module is not importable",
    )


def pytest_runtest_setup(item: Item) -> None:
    marker = item.get_closest_marker("requires_module")
    if not marker:
        return
    if not marker.args:
        return
    mod = str(marker.args[0])
    if importlib.util.find_spec(mod) is None:
        pytest.skip(f"optional dependency missing: {mod}")


class _DummyQtType:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __call__(self, *args: object, **kwargs: object) -> None:
        return None


def _qt_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)

    def __getattr__(attr: str) -> type[_DummyQtType]:
        _ = attr
        return _DummyQtType

    mod.__getattr__ = __getattr__  # type: ignore[attr-defined]
    return mod


@pytest.fixture
def stub_pyside6(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install lightweight PySide6 stubs for tests that only need imports."""

    pyside6 = types.ModuleType("PySide6")
    pyside6.__path__ = []
    monkeypatch.setitem(sys.modules, "PySide6", pyside6)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", _qt_module("PySide6.QtCore"))
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", _qt_module("PySide6.QtWidgets"))
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", _qt_module("PySide6.QtGui"))

    qtuitools = _qt_module("PySide6.QtUiTools")
    cast(Any, qtuitools).QUiLoader = _DummyQtType
    monkeypatch.setitem(sys.modules, "PySide6.QtUiTools", qtuitools)
