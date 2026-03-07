from __future__ import annotations

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine, HipStepInputs, HipUiInputs
from steuerung3d.core.intents import ClaimAxis, EnableAxis, JogWinch, ReleaseAxis
from steuerung3d.core.joy_state import JoyState
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
    axis_id: str,
    *,
    joy: JoyState | None = None,
    claimed_by: str = "",
    vel_max: float = 1.0,
) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="LIVE",
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
        params={"VelMax": float(vel_max)},
        estop_status_word=_ready_estop_word(),
        joy=joy if joy is not None else JoyState(),
    )


def test_no_selected_lane_does_not_claim_axis_under_lane_semantics() -> None:
    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=True, soll_speed=0.0)
    snap = _snap("Anton", joy=joy, claimed_by="")

    inputs = HipStepInputs(
        snap=snap,
        hip_id="hip-test",
        last_rx_ns=0,
        now_ns=0,
        stale_after_ms=500,
        fixed_axis="",
        lock_axis_combo=False,
        last_mode="IDLE",
        last_estate="IDLE",
        ui=_ui("Anton"),
        core_acks=[],
        joy=joy,
    )

    res = eng.step(inputs)
    assert not any(isinstance(i, ClaimAxis) for i in res.intents)
    assert not any(isinstance(i, ReleaseAxis) for i in res.intents)


def test_no_selected_lane_without_ownership_does_not_move_axis() -> None:
    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=True, soll_speed=0.5)
    snap = _snap("Anton", joy=joy, claimed_by="", vel_max=2.0)

    inputs = HipStepInputs(
        snap=snap,
        hip_id="hip-test",
        last_rx_ns=0,
        now_ns=0,
        stale_after_ms=500,
        fixed_axis="",
        lock_axis_combo=False,
        last_mode="IDLE",
        last_estate="IDLE",
        ui=_ui("Anton"),
        core_acks=[],
        joy=joy,
    )

    res = eng.step(inputs)
    assert not any(isinstance(i, ClaimAxis) for i in res.intents)
    assert not any(isinstance(i, EnableAxis) and i.enable for i in res.intents)
    assert not any(isinstance(i, JogWinch) and abs(float(i.rate)) > 1e-9 for i in res.intents)


def test_selected_lane_with_ownership_drives_motion_but_not_attachment() -> None:
    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=True, soll_speed=0.4, selected_axes=("Anton",))
    snap = _snap("Anton", joy=joy, claimed_by="hip-test", vel_max=2.0)

    inputs = HipStepInputs(
        snap=snap,
        hip_id="hip-test",
        last_rx_ns=0,
        now_ns=0,
        stale_after_ms=500,
        fixed_axis="",
        lock_axis_combo=False,
        last_mode="IDLE",
        last_estate="IDLE",
        ui=_ui("Anton"),
        core_acks=[],
        joy=joy,
    )

    res = eng.step(inputs)
    assert not any(isinstance(i, ClaimAxis) for i in res.intents)
    assert not any(isinstance(i, ReleaseAxis) for i in res.intents)
    assert any(isinstance(i, EnableAxis) and i.enable for i in res.intents)
    assert any(
        isinstance(i, JogWinch) and i.winch_id == "Anton" and i.rate == 0.8 for i in res.intents
    )
