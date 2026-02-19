from __future__ import annotations

import logging

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine, HipUiInputs
from steuerung3d.apps.yellow.runtimes.hip_runtime import HipRuntime, HipRuntimeInputs
from steuerung3d.core.intents import ClaimAxis
from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat


def _runtime() -> HipRuntime:
    engine = HipEngine(hip_id="hip-test")
    hb = Heartbeat("hi_p", interval_s=1.0)
    ch = ChangeTracker()
    return HipRuntime(
        engine=engine,
        hb=hb,
        ch=ch,
        status=None,
        stale_after_ms=5,
        log=logging.getLogger("test.hip_runtime"),
        hip_id="hip-test",
        shadow_mode="old",
    )


def _snap(axis_id: str = "A", device_tick: int = 10) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        mode="IDLE",
        estop=False,
        fault=False,
        axes={
            axis_id: AxisTelemetry(
                pos=0.0,
                vel=0.0,
                enabled=True,
                fault=False,
                device_tick=device_tick & 0xFFFF,
            )
        },
    )


def test_hip_runtime_sets_startup_on_stale_gap() -> None:
    rt = _runtime()
    ui = HipUiInputs(
        axis_selected="",
        axis_selection_changed=False,
        estop_reset_clicked=False,
        resync_clicked=False,
        param_actions=[],
        param_values={},
    )

    res = rt.tick(inputs=HipRuntimeInputs(snaps=[_snap()], now_ns=10_000_000, ui=ui))
    assert res.view_model is not None
    assert res.apply_startup_state is False

    res2 = rt.tick(inputs=HipRuntimeInputs(snaps=[], now_ns=16_000_000, ui=ui))
    assert res2.apply_startup_state is True


def test_hip_runtime_emits_claim_axis_intent() -> None:
    rt = _runtime()
    ui = HipUiInputs(
        axis_selected="A",
        axis_selection_changed=True,
        estop_reset_clicked=False,
        resync_clicked=False,
        param_actions=[],
        param_values={},
    )

    res = rt.tick(inputs=HipRuntimeInputs(snaps=[_snap("A")], now_ns=10_000_000, ui=ui))
    assert any(isinstance(intent, ClaimAxis) for intent in res.intents)
