from __future__ import annotations

import json

from qt_panda_spike.backends.base import PickRequest
from qt_panda_spike.ui.pick_log import PickLog


def test_pick_request_record_contains_normalized_coords() -> None:
    request = PickRequest(
        widget_x=200.0,
        widget_y=100.0,
        widget_width=800.0,
        widget_height=600.0,
        display_x=10.0,
        display_y=20.0,
        display_width=780.0,
        display_height=560.0,
        image_x=480.0,
        image_y=135.0,
        image_width=960.0,
        image_height=540.0,
    )

    record = request.to_record()

    assert record["image"]["normalized_x"] == 0.0
    assert record["image"]["normalized_y"] == 0.5


def test_pick_log_appends_json_line(tmp_path) -> None:
    log_path = tmp_path / "pick.jsonl"
    log = PickLog(log_path)

    log.append({"backend": "offscreen", "request": {"widget": {"x": 1.0, "y": 2.0}}})

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["backend"] == "offscreen"
    assert payload["request"]["widget"]["x"] == 1.0
    assert "timestamp_utc" in payload
