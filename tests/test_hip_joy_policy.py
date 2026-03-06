from __future__ import annotations


from steuerung3d.apps.yellow.engines.hip.engine import HipEngine, HipStepInputs, HipUiInputs
from steuerung3d.core.intents import ClaimAxis, EnableAxis, JogAxis, JogWinch
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
    estop_word: int | None = None,
) -> TelemetrySnapshot:
    densis = {}
    if claimed_by is not None:
        densis = {
            axis_id: DensiTelemetry(
                device_id=axis_id,
                online=True,
                claimed_by_hip=str(claimed_by or ""),
                participating=False,
                anchor_xyz=None,
                last_seen_age_ticks=0,
            )
        }
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={axis_id: AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False)},
        densis=densis,
        params={"VelMax": float(vel_max)},
        estop_status_word=int(_ready_estop_word() if estop_word is None else estop_word),
        joy=joy if joy is not None else JoyState(),
    )


def test_deadman_false_gates_motion_intents() -> None:
    eng = HipEngine(hip_id="hip-test")
    intents = [
        ClaimAxis(axis_id="Anton", hip_id="hip-test"),
        JogAxis(axis_id="Anton", vel=1.0, hip_id="hip-test"),
    ]
    gated = eng._gate_motion_intents(intents, deadman=False)
    assert any(isinstance(i, ClaimAxis) for i in gated)
    assert not any(isinstance(i, JogAxis) for i in gated)


def test_soll_speed_negative_is_clamped_and_stored() -> None:
    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=True, select_hip=False, soll_speed=-1.5)
    snap = _snap("Anton", joy=joy, claimed_by="hip-test")

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

    eng.step(inputs)
    assert eng.state.joy.soll_speed == -1.0


def test_soll_speed_emits_jog_winch_when_deadman_held() -> None:
    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=True, select_hip=True, soll_speed=0.4)
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
    assert any(isinstance(i, EnableAxis) and i.axis_id == "Anton" and i.enable for i in res.intents)
    assert any(
        isinstance(i, JogWinch) and i.winch_id == "Anton" and i.rate == 0.8 for i in res.intents
    )


def test_soll_speed_negative_emits_jog_when_ready() -> None:
    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=True, select_hip=True, soll_speed=-0.5)
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
    assert any(
        isinstance(i, JogWinch) and i.winch_id == "Anton" and i.rate == -1.0 for i in res.intents
    )


def test_not_owner_blocks_jog() -> None:
    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=True, select_hip=True, soll_speed=0.5)
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
    assert not any(isinstance(i, JogWinch) and abs(float(i.rate)) > 1e-6 for i in res.intents)


def test_deadman_false_blocks_jog() -> None:
    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=False, select_hip=True, soll_speed=0.5)
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
    assert not any(isinstance(i, JogWinch) and abs(float(i.rate)) > 1e-6 for i in res.intents)


def test_soll_speed_repeat_is_throttled() -> None:
    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=True, select_hip=False, soll_speed=0.2)
    snap = _snap("Anton", joy=joy, claimed_by="hip-test", vel_max=1.5)

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

    res1 = eng.step(inputs)
    res2 = eng.step(inputs)
    assert any(isinstance(i, JogWinch) and i.rate == 0.0 for i in res1.intents)
    assert not any(isinstance(i, JogWinch) for i in res2.intents)


def test_single_actionable_axis_fallback_selects_in_scope_axis() -> None:
    class _AxisWithScope:
        def __init__(self, *, in_scope: bool, fault: bool = False) -> None:
            self.pos = 0.0
            self.vel = 0.0
            self.enabled = True
            self.fault = fault
            self.in_scope = in_scope

    eng = HipEngine(hip_id="hip-test")
    joy = JoyState(deadman=True, select_hip=True, soll_speed=0.5)
    axes = {
        "Anton": _AxisWithScope(in_scope=True, fault=False),
        "Debby": _AxisWithScope(in_scope=False, fault=False),
    }
    densis = {
        "Anton": DensiTelemetry(
            device_id="Anton",
            online=True,
            claimed_by_hip="hip-test",
            participating=False,
            anchor_xyz=None,
            last_seen_age_ticks=0,
        ),
        "Debby": DensiTelemetry(
            device_id="Debby",
            online=True,
            claimed_by_hip="other",
            participating=False,
            anchor_xyz=None,
            last_seen_age_ticks=0,
        ),
    }
    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes=axes,
        densis=densis,
        params={"VelMax": 2.0},
        estop_status_word=_ready_estop_word(),
        joy=joy,
    )

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
        ui=_ui(""),
        core_acks=[],
        joy=joy,
    )

    res = eng.step(inputs)
    assert any(isinstance(i, EnableAxis) and i.axis_id == "Anton" and i.enable for i in res.intents)
    assert any(
        isinstance(i, JogWinch) and i.winch_id == "Anton" and i.rate == 1.0 for i in res.intents
    )
