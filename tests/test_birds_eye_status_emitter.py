from __future__ import annotations

from steuerung3d.core.status import StatusEmitter


def test_status_emitter_emit_every_accepts_empty_fields() -> None:
    emitter = StatusEmitter(("127.0.0.1", 9), "", "test", "", 123, min_period_s=0.0)
    emitter.emit_every(level="OK", summary="", fields={})
