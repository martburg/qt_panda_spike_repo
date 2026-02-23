from __future__ import annotations

from steuerung3d.core.stack_runtime import format_birds_eye


def test_format_birds_eye_multiline() -> None:
    parts = ["svc-a: OK axis=A core_mode=IDLE (12ms)", "svc-b: WARN stale (250ms)"]
    out = format_birds_eye(parts, multiline=True, max_entries=6, max_width=80)
    assert "[birds-eye]" in out
    assert "\n" in out
    assert "svc-a" in out


def test_format_birds_eye_single_line() -> None:
    parts = ["svc-a: OK axis=A core_mode=IDLE (12ms)"]
    out = format_birds_eye(parts, multiline=False)
    assert out.startswith("[birds]")
    assert "\n" not in out
