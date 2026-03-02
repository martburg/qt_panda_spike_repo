from __future__ import annotations

from typing import Iterable

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine, HipStepInputs, HipUiInputs
from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.executor import build_command_frame
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import EnableAxis, JogWinch, JoyStateUpdate, RequestAxisLease
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot
from steuerung3d.protocol.estop_bits import ESTOP_CAUSE_KEYS, ESTOP_OK_KEYS, encode_estop_word


def _ui(axis_id: str) -> HipUiInputs:
    return HipUiInputs(
        axis_selected=axis_id,
        axis_selection_changed=False,
        estop_reset_clicked=False,
        resync_clicked=False,
        main_reset_clicked=False,
        guider_reset_clicked=False,
        param_actions=[],
        param_values={},
    )


def _ready_estop_word() -> int:
    bits = {k: True for k in ESTOP_OK_KEYS}
    bits["taster"] = True
    bits["schuetz"] = True
    for k in ESTOP_CAUSE_KEYS:
        bits[k] = False
    return encode_estop_word(bits)


def _snap(
    axis_id: str, *, joy: JoyState, claimed_by: str, vel_max: float = 1.0
) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={axis_id: AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False)},
        estop_status_word=_ready_estop_word(),
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
        params={"VelMax": float(vel_max)},
        joy=joy,
    )


def _step_engine(
    *,
    axis_id: str,
    joy: JoyState,
    claimed_by: str,
    hip_id: str,
    vel_max: float = 1.0,
) -> list[object]:
    eng = HipEngine(hip_id=hip_id)
    snap = _snap(axis_id, joy=joy, claimed_by=claimed_by, vel_max=vel_max)
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

    # A) deadman false => JogWinch(0) + EnableAxis(False)
    joy = JoyState(deadman=False, select_hip=False, soll_speed=0.8)
    intents = _step_engine(axis_id=axis_id, joy=joy, claimed_by=hip_id, hip_id=hip_id)
    assert any(isinstance(i, JogWinch) and i.rate == 0.0 for i in intents)
    assert any(isinstance(i, EnableAxis) and i.enable is False for i in intents)

    # B) deadman true + selected + owned => EnableAxis(True) + JogWinch with scaled sign
    joy = JoyState(deadman=True, select_hip=True, soll_speed=-0.6)
    intents = _step_engine(axis_id=axis_id, joy=joy, claimed_by=hip_id, hip_id=hip_id, vel_max=2.0)
    assert any(isinstance(i, EnableAxis) and i.enable is True for i in intents)
    assert any(isinstance(i, JogWinch) and i.rate == -1.2 for i in intents)

    st = MachineState()
    st.core_mode = CoreMode.LIVE
    st.joy = JoyState(select_hip=True)
    apply_intent(st, RequestAxisLease(axis_id=axis_id, hip_id=hip_id, req_id="lease-anton"))
    apply_intent(st, EnableAxis(axis_id=axis_id, enable=True, hip_id=hip_id))
    _apply_intents(st, intents)

    cmd = build_command_frame(st)
    assert cmd.axes[axis_id].vel == -1.2

    # C) owned false => no JogWinch (allow stop intent)
    joy = JoyState(deadman=True, select_hip=False, soll_speed=0.4)
    intents = _step_engine(axis_id=axis_id, joy=joy, claimed_by="other", hip_id=hip_id)
    assert not any(isinstance(i, JogWinch) and abs(float(i.rate)) > 1e-6 for i in intents)
    assert not any(isinstance(i, EnableAxis) and i.enable for i in intents)


def test_joy_state_update_does_not_drive_motion() -> None:
    axis_id = "Anton"
    hip_id = "hip-test"

    st = MachineState()
    st.ensure_axis(axis_id)
    st.core_mode = CoreMode.LIVE
    apply_intent(st, RequestAxisLease(axis_id=axis_id, hip_id=hip_id, req_id="lease-joy"))
    apply_intent(st, EnableAxis(axis_id=axis_id, enable=True, hip_id=hip_id))

    apply_intent(st, JoyStateUpdate(deadman=True, select_hip=False, soll_speed=-1.0))

    cmd = build_command_frame(st)
    assert cmd.axes[axis_id].vel == 0.0


def test_core_select_gates_speed_when_unselected() -> None:
    axis_id = "Anton"
    hip_id = "hip-test"

    st = MachineState()
    st.ensure_axis(axis_id)
    st.core_mode = CoreMode.LIVE
    apply_intent(st, RequestAxisLease(axis_id=axis_id, hip_id=hip_id, req_id="lease-sel-0"))
    apply_intent(st, EnableAxis(axis_id=axis_id, enable=True, hip_id=hip_id))
    apply_intent(st, JogWinch(winch_id=axis_id, rate=0.7, hip_id=hip_id))
    apply_intent(st, JoyStateUpdate(deadman=True, select_hip=False, soll_speed=0.7))

    cmd = build_command_frame(st)
    assert cmd.axes[axis_id].vel == 0.0


def test_core_select_allows_speed_when_selected() -> None:
    axis_id = "Anton"
    hip_id = "hip-test"

    st = MachineState()
    st.ensure_axis(axis_id)
    st.core_mode = CoreMode.LIVE
    apply_intent(st, RequestAxisLease(axis_id=axis_id, hip_id=hip_id, req_id="lease-sel-1"))
    apply_intent(st, EnableAxis(axis_id=axis_id, enable=True, hip_id=hip_id))
    apply_intent(st, JogWinch(winch_id=axis_id, rate=-0.4, hip_id=hip_id))
    apply_intent(st, JoyStateUpdate(deadman=True, select_hip=True, soll_speed=-0.4))

    cmd = build_command_frame(st)
    assert cmd.axes[axis_id].vel == -0.4
