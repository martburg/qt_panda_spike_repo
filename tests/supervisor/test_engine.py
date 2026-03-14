from __future__ import annotations

from steuerung3d.apps.supervisor.engine import SupervisorEngine
from steuerung3d.apps.supervisor.models import PairConfig, PairPhase, SupervisorProfile
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, JoyState, TelemetrySnapshot
from steuerung3d.protocol.estop_bits import (
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    ESTOP_SPECS,
    encode_estop_word,
)


def _profile() -> SupervisorProfile:
    return SupervisorProfile(
        supervisor_id="sup",
        title="Supervisor",
        cycle_ms=50,
        telem_in="127.0.0.1:51002",
        intent_out="127.0.0.1:51001",
        pairs=(
            PairConfig(
                pair_id="anton",
                axis_id="Anton",
                densi_id="Anton",
                hip_id="hip_anton",
                selected=True,
                densi_action_out="127.0.0.1:53001",
            ),
        ),
    )


def _healthy_word(*, taster: bool = False, brk_ok: bool = True) -> int:
    bits: dict[str, bool] = {}
    for key in ESTOP_SPECS:
        if key in ESTOP_OK_KEYS:
            bits[key] = True
        elif key in ESTOP_CAUSE_KEYS:
            bits[key] = False
        else:
            bits[key] = False
    bits["schuetz"] = True
    bits["taster"] = taster
    bits["brk1_ok"] = brk_ok
    bits["brk2_ok"] = brk_ok
    return encode_estop_word(bits)


def _snap(
    *,
    estop_word: int,
    vel: float = 0.0,
    joy_deadman: bool = False,
    soll_speed: float = 0.0,
    age_ticks: int = 0,
) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.05,
        core_mode="RUN",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(
                pos=1.0,
                vel=vel,
                enabled=True,
                fault=False,
                device_tick=12,
                lifetick_age=0,
            )
        },
        densis={
            "Anton": DensiTelemetry(device_id="Anton", online=True, last_seen_age_ticks=age_ticks)
        },
        axis_estop_status_word={"Anton": estop_word},
        joy=JoyState(deadman=joy_deadman, soll_speed=soll_speed),
    )


def test_engine_maps_ready_live_and_stale() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11) | (1 << 27) | (1 << 13) | (1 << 20) | (1 << 21), vel=0.0))
    row = eng.snapshot().rows[0]
    assert row.phase in (PairPhase.ARMED, PairPhase.READY, PairPhase.ESTOP)

    eng.ingest(
        _snap(
            estop_word=(1 << 11) | (1 << 27) | (1 << 13) | (1 << 20) | (1 << 21),
            vel=0.2,
            joy_deadman=True,
            soll_speed=0.5,
        )
    )
    assert eng.snapshot().rows[0].phase == PairPhase.LIVE

    eng.ingest(_snap(estop_word=(1 << 11), age_ticks=50))
    assert eng.snapshot().rows[0].phase == PairPhase.STALE


def test_selection_changes_joy_update_selected_axes() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11)))
    batch = eng.consume_outbound()
    assert batch.intents[-1].selected_axes == ("Anton",)
    eng.set_selected("anton", False)
    batch = eng.consume_outbound()
    assert batch.intents[-1].selected_axes == ()


def test_estart_and_chk_request_emit_remote_densi_actions() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11)))
    eng.queue_estart()
    eng.set_chk_requested(True)
    batch = eng.consume_outbound()
    assert batch.densi_actions["anton"][0].action == "estart"
    assert batch.densi_actions["anton"][1].action == "chk_es_taster"
    assert batch.densi_actions["anton"][1].value is True


def test_status_line_uses_arming_when_pair_is_armed() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=_healthy_word(taster=True, brk_ok=False)))
    snap = eng.snapshot()
    assert snap.rows[0].phase in (PairPhase.ARMED, PairPhase.READY)
    if snap.rows[0].phase == PairPhase.ARMED:
        assert "System: ARMING" in snap.status_text
