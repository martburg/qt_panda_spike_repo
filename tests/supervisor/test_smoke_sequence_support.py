from __future__ import annotations

from pathlib import Path

from steuerung3d.apps.supervisor.models import AxisConfig, SupervisorProfile
from steuerung3d.apps.supervisor.smoke_sequence_support import (
    SmokeSequenceResult,
    build_selected_estart_targets,
    build_selected_estop_reset_intents,
    build_selected_resync_intents,
    densi_process_names_for_axes,
    extract_axis_device_ticks,
    extract_axis_estates,
    extract_axis_positions,
    extract_axis_system_time_tokens,
    extract_axis_velocities,
    infer_observer_telemetry_candidates,
    parse_system_time_token,
    system_time_tokens_advanced,
)
from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot
from steuerung3d.protocol.estop_bits import (
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    ESTOP_SPECS,
    encode_estop_word,
)


def _profile() -> SupervisorProfile:
    return SupervisorProfile(
        supervisor_id="sup_smoke",
        title="Smoke",
        cycle_ms=50,
        telem_in="127.0.0.1:51002",
        intent_out="127.0.0.1:51001",
        axes=(
            AxisConfig(
                axis_id="Anton",
                unit_id="anton",
                selected=True,
                densi_action_out="127.0.0.1:52011",
            ),
            AxisConfig(
                axis_id="Debby",
                unit_id="debby",
                selected=False,
                densi_action_out="127.0.0.1:52012",
            ),
            AxisConfig(axis_id="Cecil", unit_id="cecil", selected=True),
        ),
    )


def _healthy_word(*, taster: bool, brk_ok: bool) -> int:
    bits: dict[str, bool] = {}
    for key in ESTOP_SPECS:
        if key in ESTOP_OK_KEYS:
            bits[key] = True
        elif key in ESTOP_CAUSE_KEYS:
            bits[key] = False
        else:
            bits[key] = False
    bits["schuetz"] = True
    bits["taster"] = bool(taster)
    bits["brk1_ok"] = bool(brk_ok)
    bits["brk2_ok"] = bool(brk_ok)
    return int(encode_estop_word(bits))


def test_build_selected_estop_reset_intents_uses_supervisor_actor_and_selected_axes() -> None:
    intents = build_selected_estop_reset_intents(_profile())

    assert [intent.axis_id for intent in intents] == ["Anton", "Cecil"]
    assert all(intent.hip_id == "sup_smoke" for intent in intents)
    assert all(intent.actor_kind == "supervisor" for intent in intents)


def test_build_selected_resync_intents_uses_supervisor_actor_and_selected_axes() -> None:
    intents = build_selected_resync_intents(_profile())

    assert [intent.axis_id for intent in intents] == ["Anton", "Cecil"]
    assert all(intent.hip_id == "sup_smoke" for intent in intents)
    assert all(intent.actor_kind == "supervisor" for intent in intents)


def test_build_selected_estart_targets_uses_only_selected_axes_with_action_out() -> None:
    targets = build_selected_estart_targets(_profile())

    assert [target.axis_id for target in targets] == ["Anton"]
    assert targets[0].densi_process_name == "densi-Anton"
    assert targets[0].action_out_addr == "127.0.0.1:52011"


def test_densi_process_names_follow_stack_runtime_naming() -> None:
    assert densi_process_names_for_axes(("Anton", "Debby")) == ("densi-Anton", "densi-Debby")


def test_infer_observer_telemetry_candidates_prefers_free_fanout_slots() -> None:
    assert infer_observer_telemetry_candidates(_profile()) == (
        ("127.0.0.1", 51003),
        ("127.0.0.1", 51004),
        ("127.0.0.1", 51005),
    )


def test_parse_system_time_token_accepts_densi_wallclock_format() -> None:
    parsed = parse_system_time_token("18-03-2026 22:33:16 451 ms")

    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 3
    assert parsed.day == 18
    assert parsed.hour == 22
    assert parsed.minute == 33
    assert parsed.second == 16
    assert parsed.microsecond == 451000


def test_system_time_tokens_advanced_accepts_later_token() -> None:
    assert system_time_tokens_advanced(
        "18-03-2026 22:33:16 451 ms",
        "18-03-2026 22:33:16 490 ms",
    )


def test_extract_axis_system_time_tokens_reads_axis_tail_cache() -> None:
    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={},
        axis_plc_uplink_tail={
            "Anton": {"SystemTime": "18-03-2026 22:33:16 451 ms"},
            "Debby": {"SystemTime": "18-03-2026 22:33:16 452 ms"},
        },
    )

    assert extract_axis_system_time_tokens(snap, ("Anton", "Debby", "Cecil")) == {
        "Anton": "18-03-2026 22:33:16 451 ms",
        "Debby": "18-03-2026 22:33:16 452 ms",
    }


def test_extract_axis_estates_reads_axis_estop_word_cache() -> None:
    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={},
        axis_estop_status_word={
            "Anton": _healthy_word(taster=False, brk_ok=True),
            "Debby": _healthy_word(taster=True, brk_ok=False),
            "Cecil": _healthy_word(taster=True, brk_ok=True),
        },
    )

    assert extract_axis_estates(snap, ("Anton", "Debby", "Cecil")) == {
        "Anton": "IDLE",
        "Debby": "ARMED",
        "Cecil": "READY",
    }


def test_smoke_sequence_result_exposes_publish_counts_for_cli_feedback() -> None:
    result = SmokeSequenceResult(
        session_dir=Path(".run/example"),
        selected_axis_ids=("Anton",),
        observed_reset_log_names=("densi-Anton",),
        observed_estart_log_names=("densi-Anton",),
        observed_system_time_axis_ids=("Anton",),
        system_time_first_by_axis={"Anton": "18-03-2026 22:33:16 451 ms"},
        system_time_last_by_axis={"Anton": "18-03-2026 22:33:16 490 ms"},
        system_time_first_tick_by_axis={"Anton": 101},
        system_time_last_tick_by_axis={"Anton": 144},
        reset_publish_count=3,
        estart_publish_count=2,
        resync_publish_count=4,
        chk_taster_publish_count=5,
        observed_chk_ready_axis_ids=("Anton",),
        chk_phase_before_by_axis={"Anton": "IDLE"},
        chk_phase_first_active_by_axis={"Anton": "ARMED"},
        chk_phase_final_by_axis={"Anton": "READY"},
        chk_armed_axis_ids=("Anton",),
        chk_ready_axis_ids=("Anton",),
        motion_command_publish_count=3,
        observed_motion_axis_ids=("Anton",),
        observed_stop_axis_ids=("Anton",),
        motion_start_pos_by_axis={"Anton": 1.0},
        motion_end_pos_by_axis={"Anton": 1.35},
        motion_delta_by_axis={"Anton": 0.35},
        motion_max_abs_vel_by_axis={"Anton": 0.42},
        motion_final_abs_vel_by_axis={"Anton": 0.0},
    )

    assert result.reset_publish_count == 3
    assert result.estart_publish_count == 2
    assert result.system_time_last_by_axis == {"Anton": "18-03-2026 22:33:16 490 ms"}
    assert result.system_time_last_tick_by_axis == {"Anton": 144}
    assert result.resync_publish_count == 4
    assert result.chk_taster_publish_count == 5
    assert result.chk_phase_first_active_by_axis == {"Anton": "ARMED"}
    assert result.chk_phase_final_by_axis == {"Anton": "READY"}
    assert result.motion_command_publish_count == 3
    assert result.motion_delta_by_axis == {"Anton": 0.35}


def test_extract_axis_device_ticks_reads_axis_device_tick_cache() -> None:
    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(pos=0.0, vel=0.0, enabled=False, fault=False, device_tick=101),
            "Debby": AxisTelemetry(pos=0.0, vel=0.0, enabled=False, fault=False, device_tick=202),
        },
    )

    assert extract_axis_device_ticks(snap, ("Anton", "Debby", "Cecil")) == {
        "Anton": 101,
        "Debby": 202,
    }


def test_extract_axis_positions_and_velocities_read_axis_cache() -> None:
    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(pos=1.25, vel=0.30, enabled=True, fault=False),
            "Debby": AxisTelemetry(pos=-0.50, vel=-0.10, enabled=True, fault=False),
        },
    )

    assert extract_axis_positions(snap, ("Anton", "Debby")) == {"Anton": 1.25, "Debby": -0.5}
    assert extract_axis_velocities(snap, ("Anton", "Debby")) == {"Anton": 0.3, "Debby": -0.1}


def test_smoke_sequence_result_exposes_systemtime_tick_ranges_for_cli_feedback() -> None:
    result = SmokeSequenceResult(
        session_dir=Path(".run/example"),
        selected_axis_ids=("Anton",),
        observed_reset_log_names=("densi-Anton",),
        observed_estart_log_names=("densi-Anton",),
        observed_system_time_axis_ids=("Anton",),
        system_time_first_by_axis={"Anton": "18-03-2026 22:33:16 451 ms"},
        system_time_last_by_axis={"Anton": "18-03-2026 22:33:16 451 ms"},
        system_time_first_tick_by_axis={"Anton": 101},
        system_time_last_tick_by_axis={"Anton": 144},
        reset_publish_count=3,
        estart_publish_count=2,
        resync_publish_count=4,
        chk_taster_publish_count=2,
        observed_chk_ready_axis_ids=("Anton",),
        chk_phase_before_by_axis={"Anton": "IDLE"},
        chk_phase_first_active_by_axis={"Anton": "ARMED"},
        chk_phase_final_by_axis={"Anton": "READY"},
        chk_armed_axis_ids=("Anton",),
        chk_ready_axis_ids=("Anton",),
        motion_command_publish_count=2,
        observed_motion_axis_ids=("Anton",),
        observed_stop_axis_ids=("Anton",),
        motion_start_pos_by_axis={"Anton": 0.0},
        motion_end_pos_by_axis={"Anton": 0.4},
        motion_delta_by_axis={"Anton": 0.4},
        motion_max_abs_vel_by_axis={"Anton": 0.5},
        motion_final_abs_vel_by_axis={"Anton": 0.0},
    )

    assert result.system_time_first_tick_by_axis == {"Anton": 101}
    assert result.system_time_last_tick_by_axis == {"Anton": 144}
    assert result.resync_publish_count == 4
    assert result.chk_taster_publish_count == 2
    assert result.observed_chk_ready_axis_ids == ("Anton",)
    assert result.motion_max_abs_vel_by_axis == {"Anton": 0.5}
