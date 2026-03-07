from __future__ import annotations

import logging

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine
from steuerung3d.apps.yellow.runtimes.hip_runtime import HipRuntime
from steuerung3d.apps.yellow.runtimes.hip_runtime_status import (
    build_hip_birdseye_payload,
    build_hip_motion_debug_snapshot,
)
from steuerung3d.core.intents import JogWinch
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat


def _runtime() -> HipRuntime:
    engine = HipEngine(hip_id="hip-test")
    engine.state.selected_axis = "Anton"
    engine.state.joy = JoyState(deadman=True, selected_axes=("Anton",), soll_speed=0.5)
    return HipRuntime(
        engine=engine,
        hb=Heartbeat("hi_p_test"),
        ch=ChangeTracker(),
        status=None,
        stale_after_ms=500,
        log=logging.getLogger("hip_test"),
        hip_id="hip-test",
    )


def _snap() -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False),
        },
        params={"VelMax": 2.0},
        joy=JoyState(deadman=True, selected_axes=("Anton",), soll_speed=0.5),
    )


def test_motion_debug_builder_uses_runtime_axis_selection() -> None:
    rt = _runtime()
    snap = _snap()

    dbg = build_hip_motion_debug_snapshot(runtime=rt, snap=snap)

    assert dbg.motion_axis == "Anton"
    assert dbg.core_mode == "LIVE"
    assert dbg.joy_deadman is True
    assert dbg.joy_select_hip is True
    assert abs(dbg.joy_soll_speed - 0.5) < 1e-6


def test_birdseye_builder_includes_rate_and_intent_types() -> None:
    rt = _runtime()
    snap = _snap()

    payload = build_hip_birdseye_payload(
        runtime=rt,
        snap=snap,
        intents=[JogWinch(winch_id="Anton", rate=1.0, hip_id="hip-test")],
        estate="READY",
        soft_errors={"binder.apply": 2},
    )

    assert "hip axis=Anton" in payload.summary
    assert payload.fields["joy_rate_mps"] == 1.0
    assert payload.fields["intents_out_types"] == "JogWinch"
    assert payload.fields["soft_errors_total"] == 2


class _StatusSink:
    def __init__(self) -> None:
        self.last_level: str = ""
        self.last_summary: str = ""
        self.last_fields: dict[str, object] = {}

    def emit_every(self, *, level: str, summary: str, fields: dict[str, object]) -> None:
        self.last_level = str(level)
        self.last_summary = str(summary)
        self.last_fields = dict(fields or {})


def test_runtime_emits_birdseye_via_shared_builder() -> None:
    status = _StatusSink()
    rt = _runtime()
    rt._status = status
    snap = _snap()

    rt.emit_birdseye_motion(
        snap=snap,
        intents=[JogWinch(winch_id="Anton", rate=1.0, hip_id="hip-test")],
        estate="READY",
        soft_errors={"binder.apply": 2},
    )

    assert status.last_level == "OK"
    assert "hip axis=Anton" in status.last_summary
    assert status.last_fields["intents_out_types"] == "JogWinch"
    assert status.last_fields["soft_errors_total"] == 2
