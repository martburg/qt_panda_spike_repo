from __future__ import annotations

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine, HipStepInputs, HipUiInputs
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot


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
        mode="IDLE",
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


def test_hip_viewmodel_joy_defaults() -> None:
    axis_id = "Anton"
    eng = HipEngine(hip_id="hip-test")
    snap = _snap(axis_id, joy=JoyState())

    res = eng.step(
        HipStepInputs(
            snap=snap,
            hip_id="hip-test",
            last_rx_ns=0,
            now_ns=0,
            stale_after_ms=500,
            fixed_axis="",
            lock_axis_combo=False,
            last_mode="IDLE",
            last_estate="IDLE",
            ui=_ui(axis_id),
            core_acks=[],
            joy=snap.joy,
        )
    )

    vm = res.view_model
    assert vm.joy_deadman is False
    assert vm.joy_select_hip is False
    assert vm.joy_soll_speed == 0.0


def test_hip_viewmodel_joy_values_passthrough() -> None:
    axis_id = "Anton"
    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=True, select_hip=True, soll_speed=-0.75)
    snap = _snap(axis_id, joy=joy)

    res = eng.step(
        HipStepInputs(
            snap=snap,
            hip_id="hip-test",
            last_rx_ns=0,
            now_ns=0,
            stale_after_ms=500,
            fixed_axis="",
            lock_axis_combo=False,
            last_mode="IDLE",
            last_estate="IDLE",
            ui=_ui(axis_id),
            core_acks=[],
            joy=snap.joy,
        )
    )

    vm = res.view_model
    assert vm.joy_deadman is True
    assert vm.joy_select_hip is True
    assert vm.joy_soll_speed == -0.75
