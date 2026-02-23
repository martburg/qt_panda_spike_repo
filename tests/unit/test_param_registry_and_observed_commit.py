from __future__ import annotations

from steuerung3d.core.param_registry import normalize_group_values
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot, apply_measured_snapshot


def _snap(*, tick: int, params: dict[str, float]) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=int(tick),
        t_s=0.0,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={},
        estop_status_word=0,
        param_edit_active=False,
        param_edit_group="",
        params=dict(params),
        core_acks=[],
        param_commit_req_id="",
        param_commit_group="",
        param_commit_status="idle",
        param_commit_age_ticks=0,
        param_commit_unmatched=[],
    )


def test_normalize_pos_chain() -> None:
    vals, warnings = normalize_group_values(
        "pos",
        {"HardMax": 10, "HardMin": 0, "UserMax": -1, "UserMin": 5},
    )
    assert vals["HardMax"] == 10.0
    assert vals["HardMin"] == 0.0
    assert vals["UserMax"] == 0.0
    assert vals["UserMin"] == 0.0
    assert warnings


def test_normalize_guider_posmin_posmax() -> None:
    vals, warnings = normalize_group_values("guider", {"PosMin": 7, "PosMax": 3, "Pitch": 1})
    assert vals["PosMin"] == 3.0
    assert vals["PosMax"] == 3.0
    assert warnings


def test_observed_commit_requires_two_consecutive_matches() -> None:
    st = MachineState()
    st.param_commit_status = "pending"
    st.param_commit_desired = {"P": 1.0}
    st.param_commit_timeout_ticks = 50

    apply_measured_snapshot(st, _snap(tick=100, params={"P": 0.0}))
    assert st.param_commit_status == "pending"
    assert st.param_commit_match_streak == 0
    assert st.param_commit_observed_ticks == 1

    apply_measured_snapshot(st, _snap(tick=101, params={"P": 1.0}))
    assert st.param_commit_status == "pending"
    assert st.param_commit_match_streak == 1

    apply_measured_snapshot(st, _snap(tick=102, params={"P": 1.0}))
    assert st.param_commit_status == "applied"
    assert st.param_commit_match_streak >= 2


def test_observed_commit_timeout_pauses_when_tick_stalls() -> None:
    st = MachineState()
    st.param_commit_status = "pending"
    st.param_commit_desired = {"P": 1.0}
    st.param_commit_timeout_ticks = 2

    apply_measured_snapshot(st, _snap(tick=200, params={"P": 0.0}))
    assert st.param_commit_observed_ticks == 1

    # Duplicate tick should not advance observed_ticks or timeout.
    apply_measured_snapshot(st, _snap(tick=200, params={"P": 0.0}))
    assert st.param_commit_observed_ticks == 1
    assert st.param_commit_status == "pending"

    # Now advance tick twice => timeout.
    apply_measured_snapshot(st, _snap(tick=201, params={"P": 0.0}))
    apply_measured_snapshot(st, _snap(tick=202, params={"P": 0.0}))
    assert st.param_commit_status == "timeout"
