from __future__ import annotations

from steuerung3d.core.status import StatusEmitter


def test_status_emitter_emit_every_accepts_empty_fields() -> None:
    emitter = StatusEmitter(("127.0.0.1", 9), "", "test", "", 123, min_period_s=0.0)
    emitter.emit_every(level="OK", summary="", fields={})


from steuerung3d.apps.core_udp_service.reporter_birdseye import emit_birds_eye_status
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot


class _FakeStatus:
    def __init__(self) -> None:
        self.calls = []

    def emit_every(self, *, level="OK", summary="", fields=None) -> None:
        self.calls.append({"level": level, "summary": summary, "fields": dict(fields or {})})


class _FakeRouter:
    last_dev_estop_word_by_axis = {}


def test_birds_eye_exposes_lane_selection_and_resolved_targets() -> None:
    status = _FakeStatus()
    state = MachineState()
    state.core_mode = "LIVE"
    state.joy = JoyState(
        deadman=True, select_hip=True, soll_speed=0.5, selected_axes=("Anton", "Debby")
    )
    state.axis_claims = {"Anton": "hip-1", "Debby": "hip-2"}
    state.ensure_axis("Anton")
    state.ensure_axis("Debby")
    state.axis_cmd["Anton"].enable = True
    state.axis_cmd["Anton"].vel = 0.5
    state.axis_cmd["Debby"].enable = True
    state.axis_cmd["Debby"].vel = 0.0

    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={},
        densis={"Anton": object(), "Debby": object()},
    )

    emit_birds_eye_status(
        status=status,
        snap=snap,
        state=state,
        router=_FakeRouter(),
        axis_ids=["Anton", "Debby"],
        last_intents_meta={"count": 0, "types": []},
        last_seen={
            "intent_ts": None,
            "dev_telem_ts": None,
            "cmd_ts": None,
            "ui_telem_ts": None,
            "c2_telem_ts": None,
        },
    )

    assert status.calls, "expected birds-eye emission"
    fields = status.calls[-1]["fields"]
    assert fields["deadman"] is True
    assert fields["selected_lanes"] == ["Anton", "Debby"]
    assert fields["attached_lanes"] == ["Anton:hip-1", "Debby:hip-2"]
    assert fields["resolved_moving_targets"] == ["Anton"]
