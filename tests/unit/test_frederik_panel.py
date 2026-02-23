from __future__ import annotations

from steuerung3d.core.stack_runtime import build_frederik_panel_lines


def test_frederik_panel_contains_core_mode_and_blocked_by() -> None:
    fields = {
        "core_mode": "READY",
        "blocked_by": [
            {"code": "NO_LIVE_REQUEST", "axis_id": None, "detail": None},
        ],
        "axes": [],
    }
    text = "\n".join(build_frederik_panel_lines(fields))
    assert "core_mode=READY" in text
    assert "blocked_by=[" in text
