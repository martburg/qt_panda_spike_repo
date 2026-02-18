from __future__ import annotations

from steuerung3d.apps.yellow.engines.hip_engine import HipEngine, HipViewModel
from steuerung3d.core.intents import EchoLifeTick


def test_normalize_intents_stable_order() -> None:
    intents = [
        EchoLifeTick(axis_id="B", value=2, hip_id="h1"),
        EchoLifeTick(axis_id="A", value=1, hip_id="h1"),
    ]
    norm = HipEngine.normalize_intents(intents)
    assert norm[0][0] == "EchoLifeTick"
    assert norm[0][1][0][0] == "axis_id"
    assert norm[0][1][0][1] == "A"
    assert norm[1][1][0][1] == "B"


def test_normalize_view_model_rounds_and_casts() -> None:
    vm = HipViewModel(
        tick_text="1",
        age_ms=12.7,
        stale=False,
        lifetick_age=5.4,
        online_state="good",
        estop=False,
        fault=True,
        drive_status_summary="ok",
    )
    norm = HipEngine.normalize_view_model(vm)
    assert norm["age_ms"] == 12
    assert norm["lifetick_age"] == 5
    assert norm["stale"] is False
    assert norm["fault"] is True
