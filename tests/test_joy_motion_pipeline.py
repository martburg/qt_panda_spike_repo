from __future__ import annotations

from typing import Iterable

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine, HipStepInputs, HipUiInputs
from steuerung3d.core.executor import build_command_frame
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogWinch, JoyStateUpdate, RequestAxisLease
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.state import MachineState
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


def _snap(axis_id: str, *, joy: JoyState, claimed_by: str) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        mode="LIVE",
        estop=False,
        fault=False,
        axes={axis_id: AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False)},
        densis={
            axis_id: DensiTelemetry(
                device_id=axis_id,
                online=True,
                claimed_by_hip=str(claimed_by or ""),
                participating=False,
                anchor_xyz=None,
                last_seen_age_ticks=0,
            )
        },
        joy=joy,
    )


def _step_engine(*, axis_id: str, joy: JoyState, claimed_by: str, hip_id: str) -> list[object]:
    eng = HipEngine(hip_id=hip_id)
    snap = _snap(axis_id, joy=joy, claimed_by=claimed_by)
    inputs = HipStepInputs(
        snap=snap,
        hip_id=hip_id,
        last_rx_ns=0,
        now_ns=0,
        stale_after_ms=500,
        fixed_axis="",
        lock_axis_combo=False,
        last_mode="IDLE",
        last_estate="IDLE",
        ui=_ui(axis_id),
        core_acks=[],
        joy=joy,
    )
    result = eng.step(inputs)
    return list(result.intents or [])


def _apply_intents(state: MachineState, intents: Iterable[object]) -> None:
    for intent in intents:
        apply_intent(state, intent)


def test_joy_motion_end_to_end_gating_and_sign() -> None:
    axis_id = "Anton"
    hip_id = "hip-test"

    # A) deadman false => no JogWinch
    joy = JoyState(deadman=False, select_hip=False, soll_speed=0.8)
    intents = _step_engine(axis_id=axis_id, joy=joy, claimed_by=hip_id, hip_id=hip_id)
    assert not any(isinstance(i, JogWinch) for i in intents)

    # B) deadman true + owned => JogWinch with correct sign, drives CommandFrame vel
    joy = JoyState(deadman=True, select_hip=False, soll_speed=-0.6)
    intents = _step_engine(axis_id=axis_id, joy=joy, claimed_by=hip_id, hip_id=hip_id)
    assert any(isinstance(i, JogWinch) and i.rate == -0.6 for i in intents)

    st = MachineState()
    apply_intent(st, ArmLiveMode())
    apply_intent(st, RequestAxisLease(axis_id=axis_id, hip_id=hip_id, req_id="lease-anton"))
    apply_intent(st, EnableAxis(axis_id=axis_id, enable=True, hip_id=hip_id))
    _apply_intents(st, intents)

    cmd = build_command_frame(st)
    assert cmd.axes[axis_id].vel == -0.6

    # C) owned false => no JogWinch
    joy = JoyState(deadman=True, select_hip=False, soll_speed=0.4)
    intents = _step_engine(axis_id=axis_id, joy=joy, claimed_by="other", hip_id=hip_id)
    assert not any(isinstance(i, JogWinch) for i in intents)


def _setup_core_motion_state(*, axis_id: str, hip_id: str, vel_max: float) -> MachineState:
    st = MachineState()
    st.params["VelMax"] = float(vel_max)
    st.ensure_axis(axis_id)
    apply_intent(st, ArmLiveMode())
    apply_intent(st, RequestAxisLease(axis_id=axis_id, hip_id=hip_id, req_id="lease-joy"))
    apply_intent(st, EnableAxis(axis_id=axis_id, enable=True, hip_id=hip_id))
    return st


def test_joy_state_update_scales_velocity_by_velmax() -> None:
    axis_id = "Anton"
    hip_id = "hip-test"
    vel_max = 2.5

    st = _setup_core_motion_state(axis_id=axis_id, hip_id=hip_id, vel_max=vel_max)
    apply_intent(st, JoyStateUpdate(deadman=True, select_hip=False, soll_speed=-1.0))

    cmd = st.axis_cmd[axis_id]
    assert cmd.vel == -vel_max


def test_joy_state_update_deadman_false_stops() -> None:
    axis_id = "Anton"
    hip_id = "hip-test"
    vel_max = 2.5

    st = _setup_core_motion_state(axis_id=axis_id, hip_id=hip_id, vel_max=vel_max)
    apply_intent(st, JoyStateUpdate(deadman=False, select_hip=False, soll_speed=1.0))

    cmd = st.axis_cmd[axis_id]
    assert cmd.vel == 0.0


def test_joy_state_update_flows_into_command_frame() -> None:
    axis_id = "Anton"
    hip_id = "hip-test"
    vel_max = 1.75

    st = _setup_core_motion_state(axis_id=axis_id, hip_id=hip_id, vel_max=vel_max)
    apply_intent(st, JoyStateUpdate(deadman=True, select_hip=False, soll_speed=1.0))

    cmd = build_command_frame(st)
    assert cmd.axes[axis_id].vel == vel_max
