from __future__ import annotations

import logging
from types import SimpleNamespace

from steuerung3d.apps.yellow.engines.densi.inputs import DensiInputs, DensiUiInputs
from steuerung3d.apps.yellow.runtimes.densi_runtime_status import build_densi_status_payload
from steuerung3d.apps.yellow.runtimes.densi_runtime_tick import edge_log_cmd_changes
from steuerung3d.apps.yellow.runtimes.densi_runtime_ui_actions import apply_ui_actions


class _Axis:
    def __init__(self) -> None:
        self.vel = 0.25
        self.pos = 12.5
        self.meta = {"plc_lifetick_age_ticks": 7}


class _Tracker:
    def changed(self, key: str, value: object) -> bool:
        return True


class _EngineStub:
    def __init__(self) -> None:
        self.inj_estop_word = 0
        self.state = SimpleNamespace(estop=False, fault=False, tick=42, axes={"Anton": _Axis()})
        self.calls: list[tuple[str, object]] = []

    def inject_estop_bit(self, key: str, checked: bool) -> None:
        self.calls.append((key, checked))


def test_densi_status_payload_accepts_narrow_runtime_stub() -> None:
    runtime = SimpleNamespace(
        _last_cmd_ns=1,
        _stale_after_ms=500,
        _seen_first_cmd=True,
        _last_estop=False,
        _last_fault=False,
        _axis_ids=["Anton"],
        _last_mode="LIVE",
        _last_cmd=SimpleNamespace(
            core_mode="LIVE",
            intent=True,
            axes={"Anton": SimpleNamespace(enable=True, vel=0.5)},
        ),
        engine=SimpleNamespace(
            drive_ready=True,
            state=SimpleNamespace(
                estop=False,
                fault=False,
                tick=42,
                axes={"Anton": _Axis()},
            ),
        ),
    )

    payload = build_densi_status_payload(runtime=runtime, now_ns=2_000_000)

    assert payload.fields["axis"] == "Anton"
    assert payload.fields["cmd_enable"] is True
    debug = payload.fields.get("debug")
    assert isinstance(debug, dict)
    assert debug.get("axis_selected") == "Anton"
    assert debug.get("cmd_vel") == 0.5
    assert debug.get("vel_applied") == 0.25
    assert debug.get("lifetick_age_ticks") == 7


def test_densi_tick_helpers_accept_minimal_runtime_stub() -> None:
    records: list[str] = []

    class _Log:
        def info(self, msg: str, *args: object) -> None:
            records.append(msg % args if args else msg)

    runtime = SimpleNamespace(_ch=_Tracker(), _log=_Log())
    cmd = SimpleNamespace(core_mode="LIVE", estop_reset=True)

    edge_log_cmd_changes(runtime, cmd)

    assert any("cmd_core_mode=LIVE" in entry for entry in records)
    assert any("cmd_estop_reset=True" in entry for entry in records)


def test_densi_ui_actions_accept_minimal_runtime_stub() -> None:
    engine = _EngineStub()
    runtime = SimpleNamespace(
        engine=engine,
        _log=logging.getLogger("test.densi.ui_actions"),
        _force_refresh_checkboxes=False,
    )
    ui = DensiUiInputs()
    ui.estop_bit_toggles.append(SimpleNamespace(key="taster", checked=True))

    apply_ui_actions(runtime, DensiInputs(frames=[], now_ns=0, ui=ui))

    assert engine.calls == [("taster", True)]
    assert runtime._force_refresh_checkboxes is True
