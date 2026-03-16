from __future__ import annotations

import logging
import sys
import types
from types import SimpleNamespace

import pytest


class _DummyQtType:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return None


def _qt_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)

    def __getattr__(attr: str):
        return _DummyQtType

    mod.__getattr__ = __getattr__  # type: ignore[attr-defined]
    return mod


@pytest.fixture
def stub_pyside6(monkeypatch: pytest.MonkeyPatch) -> None:
    pyside6 = types.ModuleType("PySide6")
    pyside6.__path__ = []
    monkeypatch.setitem(sys.modules, "PySide6", pyside6)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", _qt_module("PySide6.QtCore"))
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", _qt_module("PySide6.QtWidgets"))
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", _qt_module("PySide6.QtGui"))

    qtuitools = _qt_module("PySide6.QtUiTools")
    qtuitools.QUiLoader = _DummyQtType
    monkeypatch.setitem(sys.modules, "PySide6.QtUiTools", qtuitools)


from steuerung3d.apps.yellow.binders import hip_qt_binder_apply_impl as apply_impl
from steuerung3d.apps.yellow.controllers.hip_controller import HiPController
from steuerung3d.apps.yellow.engines.hip.types import HipUiInputs
from steuerung3d.apps.yellow.runtimes.hip_runtime_impl import HipRuntimeResult


class _DummyReadoutsBindings:
    def __init__(self) -> None:
        self.txt_pos = object()


class _DummyBinder:
    def __init__(self, logger: logging.Logger) -> None:
        self.log = logger
        self._readouts_bindings = _DummyReadoutsBindings()


def _runtime_result() -> HipRuntimeResult:
    vm = SimpleNamespace(
        attach_state=SimpleNamespace(attached=True, tabs_enabled=True),
        lifetick_age=60,
        drive_status=SimpleNamespace(main_text="NoPwr NotReady FAULT -Geber"),
        readouts=SimpleNamespace(pos_text="0.00 m", vel_text="0.00 m/s"),
    )
    return HipRuntimeResult(
        snap=None,
        engine_result=None,
        view_model=vm,
        intents=[object()],
        txn_events=[],
        resync_ignored=False,
        resync_block_reason="",
        apply_startup_state=False,
        rx_count=1,
    )


def test_hip_ui_info_log_is_throttled_for_unchanged_state(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, stub_pyside6: None
) -> None:
    controller = HiPController.__new__(HiPController)
    controller._dbg_next_s = 10_000.0
    controller._dbg_vm_keys_once = True
    controller._ui_log_next_s = 0.0
    controller._last_ui_log_key = None

    ui_inputs = HipUiInputs(
        axis_selected="Anton",
        axis_selection_changed=False,
        estop_reset_clicked=False,
        resync_clicked=False,
        param_actions=[],
        param_values={},
    )
    rt_result = _runtime_result()

    monkeypatch.setattr(
        "steuerung3d.apps.yellow.controllers.hip_controller.time.time", lambda: 100.0
    )

    with caplog.at_level(logging.INFO, logger="hi_p"):
        controller._log_runtime_result(ui_inputs=ui_inputs, rt_result=rt_result)
        controller._log_runtime_result(ui_inputs=ui_inputs, rt_result=rt_result)

    ui_logs = [r for r in caplog.records if r.message.startswith("hi_p: ui axis=")]
    assert len(ui_logs) == 1


def test_hip_apply_readouts_debug_log_not_emitted_at_info(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    stub_pyside6: None,
) -> None:
    logger = logging.getLogger("hi_p.test.apply_readouts")
    binder = _DummyBinder(logger)
    vm = SimpleNamespace(readouts=SimpleNamespace())

    called = {"n": 0}
    monkeypatch.setattr(
        apply_impl,
        "apply_hip_readouts",
        lambda *args, **kwargs: called.__setitem__("n", called["n"] + 1),
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        apply_impl._apply_readouts(binder, vm)

    assert called["n"] == 1
    assert not any("dbg apply_readouts" in r.message for r in caplog.records)


def test_hip_apply_readouts_debug_log_emitted_at_debug(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    stub_pyside6: None,
) -> None:
    logger = logging.getLogger("hi_p.test.apply_readouts")
    binder = _DummyBinder(logger)
    vm = SimpleNamespace(readouts=SimpleNamespace())

    called = {"n": 0}
    monkeypatch.setattr(
        apply_impl,
        "apply_hip_readouts",
        lambda *args, **kwargs: called.__setitem__("n", called["n"] + 1),
    )

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        apply_impl._apply_readouts(binder, vm)

    assert called["n"] == 1
    assert any("dbg apply_readouts" in r.message for r in caplog.records)
