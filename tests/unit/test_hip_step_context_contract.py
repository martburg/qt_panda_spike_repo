from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from steuerung3d.apps.yellow.engines.hip.step_context import build_step_context
from steuerung3d.apps.yellow.engines.hip.types import (
    HipStepContextEngineLike,
    HipStepInputs,
    HipUiInputs,
)
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot


@dataclass
class _StubParamTxn:
    hip_id: str = ""


@dataclass
class _StubState:
    joy: JoyState = field(default_factory=JoyState)
    selected_axis: str = ""
    fixed_axis_applied: bool = False
    last_ui_axis_selected: str = ""


@dataclass
class _StubRuntime:
    state: _StubState = field(default_factory=_StubState)
    _param_txn: _StubParamTxn = field(default_factory=_StubParamTxn)


def _inputs() -> HipStepInputs:
    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.01,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(pos=0.0, vel=0.0, enabled=False, fault=False, device_tick=7),
        },
    )
    return HipStepInputs(
        snap=snap,
        hip_id="hip_anton",
        last_rx_ns=None,
        now_ns=1,
        stale_after_ms=250,
        fixed_axis="Anton",
        lock_axis_combo=True,
        last_mode="IDLE",
        last_estate="IDLE",
        ui=HipUiInputs(
            axis_selected="",
            axis_selection_changed=False,
            estop_reset_clicked=False,
            resync_clicked=False,
            param_actions=[],
            param_values={},
        ),
        core_acks=[],
        joy=JoyState(deadman=True, select_hip=True, soll_speed=0.25),
    )


def test_build_step_context_accepts_narrow_runtime_contract() -> None:
    runtime = _StubRuntime()

    ctx = build_step_context(runtime=cast(HipStepContextEngineLike, runtime), inputs=_inputs())

    assert ctx.hip_id == "hip_anton"
    assert ctx.selected_axis == "Anton"
    assert ctx.fixed_applied is True
    assert ctx.attach_combo.current == "Anton"
    assert runtime._param_txn.hip_id == "hip_anton"
    assert runtime.state.joy.deadman is True
    assert runtime.state.joy.select_hip is False
    assert runtime.state.joy.soll_speed == 0.25
