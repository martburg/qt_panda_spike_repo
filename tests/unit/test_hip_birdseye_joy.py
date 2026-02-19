from __future__ import annotations

import logging

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine
from steuerung3d.apps.yellow.runtimes.hip_runtime import HipRuntime
from steuerung3d.core.joy_state import JoyState
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat


class _FakeStatus:
    def __init__(self) -> None:
        self.last_summary = ""
        self.last_fields = {}

    def emit_every(self, *, level: str = "OK", summary: str = "", fields=None) -> None:
        self.last_summary = str(summary)
        self.last_fields = dict(fields or {})


def test_hip_birdseye_includes_joy_fields() -> None:
    engine = HipEngine(hip_id="hip-test")
    engine.state.joy = JoyState(deadman=True, select_hip=False, soll_speed=-0.5)

    runtime = HipRuntime(
        engine=engine,
        hb=Heartbeat("hi_p_test"),
        ch=ChangeTracker(),
        status=_FakeStatus(),
        stale_after_ms=500,
        log=logging.getLogger("hip_test"),
        hip_id="hip-test",
    )
    runtime._last_rx_ns = 1
    runtime._last_mode = "IDLE"
    runtime._last_estop = False
    runtime._last_fault = False

    runtime._emit_status(now_ns=2_000_000)

    status = runtime._status
    assert status is not None
    assert "JOY" in status.last_summary
    assert "dm=" in status.last_summary
    assert "sel=" in status.last_summary
    assert "sp=" in status.last_summary
    assert status.last_fields.get("joy_deadman") is True
    assert status.last_fields.get("joy_select_hip") is False
    assert abs(float(status.last_fields.get("joy_soll_speed", 0.0)) - (-0.5)) < 1e-6
