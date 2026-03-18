from __future__ import annotations

from steuerung3d.core.stack_runtime import build_frederik_panel_lines
from steuerung3d.ui.birdseye_format import BirdsEyeFields, _BirdBlockedCode


def test_frederik_panel_contains_core_mode_and_blocked_by() -> None:
    blocked_item: _BirdBlockedCode = {
        "code": "NO_LIVE_REQUEST",
        "axis_id": "",
        "detail": None,
    }
    blocked: list[_BirdBlockedCode | str] = [
        blocked_item,
    ]
    fields: BirdsEyeFields = {
        "core_mode": "READY",
        "blocked_by": blocked,
        "axes": [],
    }
    text = "\n".join(build_frederik_panel_lines(fields))
    assert "core_mode=READY" in text
    assert "blocked_by=[" in text
