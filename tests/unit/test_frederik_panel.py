from __future__ import annotations

from typing import cast

from steuerung3d.core.stack_runtime import build_frederik_panel_lines
from steuerung3d.ui.birdseye_format import BirdsEyeFields


def test_frederik_panel_contains_core_mode_and_blocked_by() -> None:
    fields = {
        "core_mode": "READY",
        "blocked_by": [
            {"code": "NO_LIVE_REQUEST", "axis_id": None, "detail": None},
        ],
        "axes": [],
    }
    text = "\n".join(build_frederik_panel_lines(cast(BirdsEyeFields, fields)))
    assert "core_mode=READY" in text
    assert "blocked_by=[" in text
