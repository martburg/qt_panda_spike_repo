import importlib.util
import pytest


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
