from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from typing import Any, cast


def _qtcore_module() -> types.ModuleType:
    m = cast(Any, types.ModuleType("PySide6.QtCore"))

    class QObject:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class _Signal:
        def connect(self, *_args, **_kwargs) -> None:
            pass

    class QTimer:
        def __init__(self, *_args, **_kwargs) -> None:
            self.timeout = _Signal()

        def start(self, *_args, **_kwargs) -> None:
            pass

    m.QObject = QObject
    m.QTimer = QTimer
    return cast(types.ModuleType, m)


def _qtwidgets_module() -> types.ModuleType:
    m = cast(Any, types.ModuleType("PySide6.QtWidgets"))

    class QApplication:
        @staticmethod
        def instance():
            return None

        def __init__(self, *_args, **_kwargs) -> None:
            self.aboutToQuit = SimpleNamespace(connect=lambda *_: None)

        def exec(self) -> int:
            return 0

    m.QApplication = QApplication
    return cast(types.ModuleType, m)


def test_refresh_hip_processes_releases_claim_and_lease_when_last_child_exits(monkeypatch) -> None:
    published: list[object] = []

    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", _qtcore_module())
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", _qtwidgets_module())

    dummy_window_mod = cast(Any, types.ModuleType("steuerung3d.apps.supervisor.gui.window"))
    dummy_window_mod.SupervisorWindow = lambda: SimpleNamespace(
        reset_estop_clicked=SimpleNamespace(connect=lambda *_: None),
        estart_clicked=SimpleNamespace(connect=lambda *_: None),
        resync_clicked=SimpleNamespace(connect=lambda *_: None),
        recover_clicked=SimpleNamespace(connect=lambda *_: None),
        chk_es_taster_changed=SimpleNamespace(connect=lambda *_: None),
        pair_selected_changed=SimpleNamespace(connect=lambda *_: None),
        open_hip_clicked=SimpleNamespace(connect=lambda *_: None),
        status_label=SimpleNamespace(setText=lambda *_: None),
        apply_snapshot=lambda *_: None,
        show=lambda: None,
        show_recover_placeholder=lambda: None,
    )
    monkeypatch.setitem(
        sys.modules,
        "steuerung3d.apps.supervisor.gui.window",
        cast(types.ModuleType, dummy_window_mod),
    )

    runtime_mod = importlib.import_module("steuerung3d.apps.supervisor.runtime")

    monkeypatch.setattr(
        runtime_mod.UdpTelemetryIn,
        "bind",
        lambda *_args, **_kwargs: SimpleNamespace(
            drain_telemetry=lambda limit=50: [],
            rx=SimpleNamespace(link=SimpleNamespace(close=lambda: None)),
        ),
    )
    monkeypatch.setattr(
        runtime_mod.UdpIntentOut,
        "connect",
        lambda *_args, **_kwargs: SimpleNamespace(
            publish_intent=published.append,
            tx=SimpleNamespace(link=SimpleNamespace(close=lambda: None)),
        ),
    )

    from steuerung3d.apps.supervisor.models import PairConfig, SupervisorProfile
    from steuerung3d.core.intents import ReleaseAxis, ReleaseAxisLease

    class _DummyChild:
        def __init__(self, rc: int | None) -> None:
            self._rc = rc

        def poll(self) -> int | None:
            return self._rc

    profile = SupervisorProfile(
        supervisor_id="sup",
        title="Supervisor",
        cycle_ms=50,
        telem_in="127.0.0.1:51002",
        intent_out="127.0.0.1:51001",
        gui=False,
        pairs=(
            PairConfig(
                pair_id="anton",
                axis_id="Anton",
                densi_id="Anton",
                hip_id="hip_anton",
                selected=True,
                densi_action_out="127.0.0.1:53001",
            ),
        ),
    )

    rt = runtime_mod.SupervisorRuntime(profile)
    rt._hip_children = {"anton": [_DummyChild(0)]}
    rt._refresh_hip_processes()

    assert rt.engine.hip_open_total == 0
    assert any(
        isinstance(i, ReleaseAxis) and i.axis_id == "Anton" and i.hip_id == "hip_anton"
        for i in published
    )
    assert any(
        isinstance(i, ReleaseAxisLease) and i.axis_id == "Anton" and i.hip_id == "hip_anton"
        for i in published
    )
