from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from typing import Any, Callable, cast


class _NullSignal:
    def connect(self, *_args: object, **_kwargs: object) -> None:
        pass


import pytest


def _qtcore_module() -> types.ModuleType:
    m = cast(Any, types.ModuleType("PySide6.QtCore"))

    class QObject:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    class _Signal:
        def connect(self, *_args: object, **_kwargs: object) -> None:
            pass

    class QTimer:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.timeout = _Signal()

        def start(self, *_args: object, **_kwargs: object) -> None:
            pass

    m.QObject = QObject
    m.QTimer = QTimer
    return cast(types.ModuleType, m)


def _qtwidgets_module() -> types.ModuleType:
    m = cast(Any, types.ModuleType("PySide6.QtWidgets"))

    class QApplication:
        @staticmethod
        def instance() -> None:
            return None

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.aboutToQuit = _NullSignal()

        def exec(self) -> int:
            return 0

    m.QApplication = QApplication
    return cast(types.ModuleType, m)


def _dummy_window_module() -> types.ModuleType:
    dummy_window_mod = cast(Any, types.ModuleType("steuerung3d.apps.supervisor.gui.window"))
    dummy_window_mod.SupervisorWindow = lambda: SimpleNamespace(
        reset_estop_clicked=_NullSignal(),
        estart_clicked=_NullSignal(),
        resync_clicked=_NullSignal(),
        recover_clicked=_NullSignal(),
        chk_es_taster_changed=_NullSignal(),
        pair_selected_changed=_NullSignal(),
        open_hip_clicked=_NullSignal(),
        status_label=SimpleNamespace(setText=_noop_text),
        apply_snapshot=_noop_apply_snapshot,
        show=_noop_show,
        show_recover_placeholder=_noop_show,
    )
    return cast(types.ModuleType, dummy_window_mod)


def _noop_text(*_args: object) -> None:
    pass


def _noop_apply_snapshot(*_args: object) -> None:
    pass


def _noop_show() -> None:
    pass


def _noop_close() -> None:
    pass


def _drain_telemetry(limit: int = 50) -> list[object]:
    _ = limit
    return []


def _drain_telemetry_stub(*_args: object, **_kwargs: object) -> object:
    return SimpleNamespace(
        drain_telemetry=_drain_telemetry,
        rx=SimpleNamespace(link=SimpleNamespace(close=_noop_close)),
    )


def _publish_intent_stub(published: list[object]) -> Callable[..., object]:
    def _connect(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(
            publish_intent=published.append,
            tx=SimpleNamespace(link=SimpleNamespace(close=_noop_close)),
        )

    return _connect


def test_refresh_hip_processes_releases_claim_and_lease_when_last_child_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    published: list[object] = []

    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", _qtcore_module())
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", _qtwidgets_module())
    monkeypatch.setitem(
        sys.modules,
        "steuerung3d.apps.supervisor.gui.window",
        _dummy_window_module(),
    )

    runtime_mod = importlib.import_module("steuerung3d.apps.supervisor.runtime")

    monkeypatch.setattr(runtime_mod.UdpTelemetryIn, "bind", _drain_telemetry_stub)
    monkeypatch.setattr(runtime_mod.UdpIntentOut, "connect", _publish_intent_stub(published))

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
    try:
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
    finally:
        rt.shutdown()


def test_supervisor_smoke_action_input_can_latch_chk_es_taster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    published_actions: list[object] = []

    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", _qtcore_module())
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", _qtwidgets_module())
    monkeypatch.setitem(
        sys.modules,
        "steuerung3d.apps.supervisor.gui.window",
        _dummy_window_module(),
    )

    runtime_mod = importlib.import_module("steuerung3d.apps.supervisor.runtime")

    monkeypatch.setattr(runtime_mod.UdpTelemetryIn, "bind", _drain_telemetry_stub)
    monkeypatch.setattr(runtime_mod.UdpIntentOut, "connect", _publish_intent_stub([]))

    def _action_out_connect(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(
            publish_action=published_actions.append,
            tx=SimpleNamespace(link=SimpleNamespace(close=_noop_close)),
        )

    def _action_in_bind(*_args: object, **_kwargs: object) -> object:
        from steuerung3d.apps.supervisor.models import DensiRemoteAction

        actions: list[DensiRemoteAction] = [DensiRemoteAction("chk_es_taster", value=True)]

        def _drain(limit: int = 100) -> list[DensiRemoteAction]:
            _ = limit
            drained = list(actions)
            actions.clear()
            return drained

        return SimpleNamespace(
            drain_actions=_drain,
            rx=SimpleNamespace(link=SimpleNamespace(close=_noop_close)),
        )

    monkeypatch.setattr(runtime_mod.UdpDensiActionOut, "connect", _action_out_connect)
    monkeypatch.setattr(runtime_mod.UdpDensiActionIn, "bind", _action_in_bind)
    monkeypatch.setenv("STEUERUNG3D_SUPERVISOR_ACTION_IN", "127.0.0.1:55001")

    from steuerung3d.apps.supervisor.models import PairConfig, SupervisorProfile
    from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot
    from steuerung3d.protocol.estop_bits import (
        ESTOP_CAUSE_KEYS,
        ESTOP_OK_KEYS,
        ESTOP_SPECS,
        encode_estop_word,
    )

    bits: dict[str, bool] = {}
    for key in ESTOP_SPECS:
        if key in ESTOP_OK_KEYS:
            bits[key] = True
        elif key in ESTOP_CAUSE_KEYS:
            bits[key] = False
        else:
            bits[key] = False
    bits["schuetz"] = True
    estop_word = int(encode_estop_word(bits))

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
    try:
        rt.engine.ingest(
            TelemetrySnapshot(
                tick=1,
                t_s=0.0,
                core_mode="IDLE",
                estop=False,
                fault=False,
                axes={
                    "Anton": AxisTelemetry(
                        pos=0.0, vel=0.0, enabled=False, fault=False, device_tick=1
                    )
                },
                densis={"Anton": DensiTelemetry(device_id="Anton", online=True)},
                axis_estop_status_word={"Anton": estop_word},
            )
        )

        rt.tick()

        assert any(
            getattr(action, "action", "") == "chk_es_taster"
            and getattr(action, "value", None) is True
            for action in published_actions
        )
    finally:
        rt.shutdown()
