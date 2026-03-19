from __future__ import annotations

from typing import Sequence

from steuerung3d.apps.supervisor.engine import SupervisorEngine
from steuerung3d.apps.supervisor.models import AxisConfig, AxisPhase, SupervisorProfile
from steuerung3d.core.intents import (
    EchoLifeTick,
    Intent,
    JoyStateUpdate,
    LocalAxisManualRequest,
    ReleaseAxisLease,
    RequestAxisLease,
    RequestEstopReset,
    RequestResync,
)
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, JoyState, TelemetrySnapshot
from steuerung3d.protocol.estop_bits import (
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    ESTOP_SPECS,
    encode_estop_word,
)


def _single_joy_update(intents: Sequence[Intent]) -> JoyStateUpdate:
    joys = [intent for intent in intents if isinstance(intent, JoyStateUpdate)]
    assert len(joys) == 1
    return joys[0]


def _echoes(intents: Sequence[Intent]) -> list[EchoLifeTick]:
    return [intent for intent in intents if isinstance(intent, EchoLifeTick)]


def _request_estop_resets(intents: Sequence[Intent]) -> list[RequestEstopReset]:
    return [intent for intent in intents if isinstance(intent, RequestEstopReset)]


def _request_resyncs(intents: Sequence[Intent]) -> list[RequestResync]:
    return [intent for intent in intents if isinstance(intent, RequestResync)]


def _request_axis_leases(intents: Sequence[Intent]) -> list[RequestAxisLease]:
    return [intent for intent in intents if isinstance(intent, RequestAxisLease)]


def _release_axis_leases(intents: Sequence[Intent]) -> list[ReleaseAxisLease]:
    return [intent for intent in intents if isinstance(intent, ReleaseAxisLease)]


def _local_manual_requests(intents: Sequence[Intent]) -> list[LocalAxisManualRequest]:
    return [intent for intent in intents if isinstance(intent, LocalAxisManualRequest)]


def _profile() -> SupervisorProfile:
    return SupervisorProfile(
        supervisor_id="sup",
        title="Supervisor",
        cycle_ms=50,
        telem_in="127.0.0.1:51002",
        intent_out="127.0.0.1:51001",
        axes=(
            AxisConfig(
                unit_id="anton",
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
                lifetick_age=7,
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
    assert row.phase in (AxisPhase.ARMED, AxisPhase.READY, AxisPhase.ESTOP)

    eng.ingest(
        _snap(
            estop_word=(1 << 11) | (1 << 27) | (1 << 13) | (1 << 20) | (1 << 21),
            vel=0.2,
            joy_deadman=True,
            soll_speed=0.5,
        )
    )
    assert eng.snapshot().rows[0].phase == AxisPhase.LIVE

    eng.ingest(_snap(estop_word=(1 << 11), age_ticks=50))
    assert eng.snapshot().rows[0].phase == AxisPhase.STALE


def test_selection_changes_joy_update_selected_axes() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11)))
    batch = eng.consume_outbound()
    assert _single_joy_update(batch.intents).selected_axes == ("Anton",)
    eng.set_selected("anton", False)
    batch = eng.consume_outbound()
    assert _single_joy_update(batch.intents).selected_axes == ()


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
    assert snap.rows[0].phase in (AxisPhase.ARMED, AxisPhase.READY)
    if snap.rows[0].phase == AxisPhase.ARMED:
        assert "System: ARMING" in snap.status_text


def test_hip_open_blocks_synchronized_motion_and_status_line() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11), joy_deadman=True, soll_speed=0.5))
    eng.set_hip_open_count("anton", 1)
    batch = eng.consume_outbound()
    joy_update = _single_joy_update(batch.intents)
    assert joy_update.deadman is False
    assert joy_update.soll_speed == 0.0
    assert joy_update.selected_axes == ()
    snap = eng.snapshot()
    assert snap.hip_open_total == 1
    assert snap.rows[0].hip_open_count == 1
    assert "hip: 1 open" in snap.status_text


def test_supervisor_row_uses_lifetick_diff_not_raw_tick() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11)))
    row = eng.snapshot().rows[0]
    assert row.livetick == 12
    assert row.livetick_diff == 7


def test_supervisor_emits_echo_using_current_axis_lifetick_and_suppresses_when_hip_open() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11)))
    batch = eng.consume_outbound()
    echoes = _echoes(batch.intents)
    joys = [i for i in batch.intents if isinstance(i, JoyStateUpdate)]
    assert len(echoes) == 1
    assert echoes[0].axis_id == "Anton"
    assert echoes[0].hip_id == "sup"
    assert echoes[0].value == 12
    assert len(joys) == 1

    eng.set_hip_open_count("anton", 1)
    batch = eng.consume_outbound()
    echoes = _echoes(batch.intents)
    assert echoes == []

    eng.set_hip_open_count("anton", 0)
    batch = eng.consume_outbound()
    echoes = _echoes(batch.intents)
    assert len(echoes) == 1
    assert echoes[0].value == 12


def test_supervisor_group_controls_and_checkbox_are_blocked_while_any_hip_is_open() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11)))
    eng.set_chk_requested(True)
    eng.queue_reset_estop()
    eng.queue_estart()
    eng.queue_resync()
    eng.set_hip_open_count("anton", 1)

    batch = eng.consume_outbound()

    assert batch.densi_actions == {}
    assert _request_estop_resets(batch.intents) == []
    assert _request_resyncs(batch.intents) == []


def test_chk_es_taster_is_forced_clear_when_first_hip_opens_and_stays_clear_after_unlock() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11)))
    eng.set_chk_requested(True)
    batch = eng.consume_outbound()
    assert batch.densi_actions["anton"][0].action == "chk_es_taster"
    assert batch.densi_actions["anton"][0].value is True

    eng.set_hip_open_count("anton", 1)
    batch = eng.consume_outbound()
    assert batch.densi_actions == {}

    eng.set_hip_open_count("anton", 0)
    batch = eng.consume_outbound()
    assert batch.densi_actions["anton"][0].action == "chk_es_taster"
    assert batch.densi_actions["anton"][0].value is False


def test_supervisor_reset_and_resync_use_supervisor_actor_and_selected_rows() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11)))
    eng.queue_reset_estop()
    eng.queue_resync()
    batch = eng.consume_outbound()
    resets = _request_estop_resets(batch.intents)
    resyncs = _request_resyncs(batch.intents)
    assert len(resets) == 1
    assert resets[0].hip_id == "sup"
    assert getattr(resets[0], "actor_kind", "") == "supervisor"
    assert len(resyncs) == 1
    assert resyncs[0].hip_id == "sup"
    assert getattr(resyncs[0], "actor_kind", "") == "supervisor"

    eng.set_selected("anton", False)
    eng.queue_reset_estop()
    eng.queue_resync()
    batch = eng.consume_outbound()
    assert _request_estop_resets(batch.intents) == []
    assert _request_resyncs(batch.intents) == []


def test_supervisor_requests_leases_and_drives_selected_axes_with_simple_1to1_kinematic() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11), joy_deadman=True, soll_speed=0.5))
    batch = eng.consume_outbound()

    leases = _request_axis_leases(batch.intents)
    manuals = _local_manual_requests(batch.intents)

    assert len(leases) == 1
    assert leases[0].axis_id == "Anton"
    assert leases[0].hip_id == "sup"
    assert len(manuals) == 1
    assert manuals[0].axis_ids == ("Anton",)
    assert manuals[0].enable is True
    assert manuals[0].rate == 0.5


def test_supervisor_releases_leases_and_stops_manual_motion_when_hip_opens() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11), joy_deadman=True, soll_speed=0.5))
    eng.consume_outbound()

    eng.set_hip_open_count("anton", 1)
    batch = eng.consume_outbound()

    releases = _release_axis_leases(batch.intents)
    manuals = _local_manual_requests(batch.intents)

    assert len(releases) == 1
    assert releases[0].axis_id == "Anton"
    assert releases[0].hip_id == "sup"
    assert len(manuals) == 1
    assert manuals[0].axis_ids == ("Anton",)
    assert manuals[0].enable is False
    assert manuals[0].rate == 0.0


def test_supervisor_releases_deselected_axis_and_disables_manual_motion_for_it() -> None:
    eng = SupervisorEngine(_profile())
    eng.ingest(_snap(estop_word=(1 << 11), joy_deadman=True, soll_speed=0.5))
    eng.consume_outbound()

    eng.set_selected("anton", False)
    batch = eng.consume_outbound()

    releases = _release_axis_leases(batch.intents)
    manuals = _local_manual_requests(batch.intents)

    assert len(releases) == 1
    assert releases[0].axis_id == "Anton"
    assert len(manuals) == 1
    assert manuals[0].axis_ids == ("Anton",)
    assert manuals[0].enable is False
    assert manuals[0].rate == 0.0
