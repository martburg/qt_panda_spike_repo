from __future__ import annotations

import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

from steuerung3d.apps.yellow.engines.densi.inputs import (
    DensiEstopToggle,
    DensiInputs,
    DensiUiInputs,
)
from steuerung3d.apps.yellow.runtimes.densi_runtime_status import build_densi_status_payload
from steuerung3d.apps.yellow.runtimes.densi_runtime_tick import edge_log_cmd_changes
from steuerung3d.apps.yellow.runtimes.densi_runtime_ui_actions import apply_ui_actions
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.util.heartbeat import ChangeTracker


class _Axis:
    def __init__(self) -> None:
        self.vel = 0.25
        self.pos = 12.5
        self.meta = {"plc_lifetick_age_ticks": 7}


@dataclass
class _PayloadRuntime:
    _last_cmd_ns: int | None
    _stale_after_ms: int
    _seen_first_cmd: bool
    _last_estop: bool
    _last_fault: bool
    _axis_ids: list[str]
    _last_mode: str
    _last_cmd: CommandFrame | None
    engine: object


@dataclass
class _TickRuntime:
    _ch: ChangeTracker
    _log: logging.Logger


@dataclass
class _UiRuntime:
    engine: object
    _log: logging.Logger
    _force_refresh_checkboxes: bool


class _EngineStub:
    def __init__(self) -> None:
        self.inj_estop_word = 0
        self.state = SimpleNamespace(estop=False, fault=False, tick=42, axes={"Anton": _Axis()})
        self.calls: list[tuple[str, object]] = []

    def inject_estop_bit(self, key: str, checked: bool) -> None:
        self.calls.append((key, checked))


def test_densi_status_payload_accepts_narrow_runtime_stub() -> None:
    runtime = _PayloadRuntime(
        _last_cmd_ns=1,
        _stale_after_ms=500,
        _seen_first_cmd=True,
        _last_estop=False,
        _last_fault=False,
        _axis_ids=["Anton"],
        _last_mode="LIVE",
        _last_cmd=CommandFrame(
            tick=0,
            t_s=0.0,
            estop=False,
            fault=False,
            core_mode="LIVE",
            intent=True,
            axes={"Anton": AxisSetpoint(enable=True, vel=0.5)},
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
    debug_map = cast(dict[str, object], debug)
    assert debug_map.get("axis_selected") == "Anton"
    assert debug_map.get("cmd_vel") == 0.5
    assert debug_map.get("vel_applied") == 0.25
    assert debug_map.get("lifetick_age_ticks") == 7


def test_densi_tick_helpers_accept_minimal_runtime_stub() -> None:
    records: list[str] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    logger = logging.getLogger("test.densi.tick_helpers")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(_ListHandler())

    runtime = _TickRuntime(_ch=ChangeTracker(), _log=logger)
    cmd = CommandFrame(
        tick=0,
        t_s=0.0,
        estop=False,
        fault=False,
        core_mode="LIVE",
        estop_reset=True,
        axes={},
    )

    edge_log_cmd_changes(runtime, cmd)

    assert any("cmd_core_mode=LIVE" in entry for entry in records)
    assert any("cmd_estop_reset=True" in entry for entry in records)


def test_densi_ui_actions_accept_minimal_runtime_stub() -> None:
    engine = _EngineStub()
    runtime = _UiRuntime(
        engine=engine,
        _log=logging.getLogger("test.densi.ui_actions"),
        _force_refresh_checkboxes=False,
    )
    ui = DensiUiInputs()
    ui.estop_bit_toggles.append(DensiEstopToggle(key="taster", checked=True))

    apply_ui_actions(runtime, DensiInputs(frames=[], now_ns=0, ui=ui))

    assert engine.calls == [("taster", True)]
    assert runtime._force_refresh_checkboxes is True
