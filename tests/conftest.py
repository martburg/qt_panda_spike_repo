import importlib.util
import sys
from pathlib import Path

import pytest


# Ensure `src/` layout works when running `pytest` directly (no editable install).
# This keeps test collection robust in fresh environments and CI.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: integration-style UDP roundtrip tests")
    config.addinivalue_line(
        "markers",
        "requires_module(name): skip test if the given Python module is not importable",
    )


def pytest_runtest_setup(item):
    marker = item.get_closest_marker("requires_module")
    if not marker:
        return
    if not marker.args:
        return
    mod = str(marker.args[0])
    if importlib.util.find_spec(mod) is None:
        pytest.skip(f"optional dependency missing: {mod}")
