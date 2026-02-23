from __future__ import annotations

import logging

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine, HipUiInputs
from steuerung3d.apps.yellow.runtimes.hip_runtime import HipRuntime, HipRuntimeInputs
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat


def _ui(axis_id: str) -> HipUiInputs:
    return HipUiInputs(
        axis_selected=axis_id,
        axis_selection_changed=False,
        estop_reset_clicked=False,
        resync_clicked=False,
        param_actions=[],
        param_values={},
    )


def _snap(axis_id: str, *, joy: JoyState) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={axis_id: AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False)},
        densis={
            axis_id: DensiTelemetry(
                device_id=axis_id,
                online=True,
                claimed_by_hip="",
                participating=False,
                anchor_xyz=None,
                last_seen_age_ticks=0,
            )
        },
        joy=joy,
    )


def _runtime() -> HipRuntime:
    engine = HipEngine(hip_id="hip-test")
    hb = Heartbeat("hi_p", interval_s=1.0)
    ch = ChangeTracker()
    return HipRuntime(
        engine=engine,
        hb=hb,
        ch=ch,
        status=None,
        stale_after_ms=500,
        log=logging.getLogger("test.hip_viewmodel_joy"),
        hip_id="hip-test",
        shadow_mode="old",
    )


def test_hip_viewmodel_joy_defaults() -> None:
    axis_id = "Anton"
    rt = _runtime()
    snap = _snap(axis_id, joy=JoyState())

    res = rt.tick(inputs=HipRuntimeInputs(snaps=[snap], now_ns=0, ui=_ui(axis_id)))
    vm = res.view_model
    assert vm.joy_deadman is False
    assert vm.joy_select_hip is False
    assert vm.joy_soll_speed == 0.0


def test_hip_viewmodel_joy_values_passthrough() -> None:
    axis_id = "Anton"
    rt = _runtime()
    joy = JoyState(deadman=True, select_hip=True, soll_speed=-0.75)
    snap = _snap(axis_id, joy=joy)

    res = rt.tick(inputs=HipRuntimeInputs(snaps=[snap], now_ns=0, ui=_ui(axis_id)))
    vm = res.view_model
    assert vm.joy_deadman is True
    assert vm.joy_select_hip is True
    assert vm.joy_soll_speed == -0.75
