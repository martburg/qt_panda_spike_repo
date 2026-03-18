from __future__ import annotations

import logging

from steuerung3d.apps.yellow.domain.banner_facts import derive_banner_estate_from_word
from steuerung3d.apps.yellow.domain.estop_facts import encode_estop_word
from steuerung3d.apps.yellow.engines.hip.engine import HipEngine
from steuerung3d.apps.yellow.runtimes.hip_runtime import HipRuntime
from steuerung3d.protocol.estop_bits import ESTOP_CAUSE_KEYS, ESTOP_OK_KEYS
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat


class _StatusSink:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def emit_every(
        self, *, level: str = "OK", summary: str = "", fields: dict[str, object] | None = None
    ) -> None:
        self.calls.append({"level": level, "summary": summary, "fields": dict(fields or {})})


def _base_bits() -> dict[str, bool]:
    bits = {k: True for k in ESTOP_OK_KEYS}
    for k in ESTOP_CAUSE_KEYS:
        bits[k] = False
    bits["schuetz"] = True
    bits["taster"] = False
    bits["brk1_ok"] = True
    bits["brk2_ok"] = True
    return bits


def test_banner_estate_mapping_basic() -> None:
    bits = _base_bits()

    bits["taster"] = False
    bits["brk1_ok"] = True
    bits["brk2_ok"] = True
    word = encode_estop_word(bits)
    assert derive_banner_estate_from_word(word, within_brake_grace=lambda: False) == "IDLE"

    bits["taster"] = True
    bits["brk1_ok"] = True
    bits["brk2_ok"] = True
    word = encode_estop_word(bits)
    assert derive_banner_estate_from_word(word, within_brake_grace=lambda: False) == "READY"

    bits["taster"] = True
    bits["brk1_ok"] = False
    bits["brk2_ok"] = True
    word = encode_estop_word(bits)
    assert derive_banner_estate_from_word(word, within_brake_grace=lambda: True) == "ARMED"

    bits["estop1"] = True
    word = encode_estop_word(bits)
    assert derive_banner_estate_from_word(word, within_brake_grace=lambda: False) == "ESTOP"


def _runtime_with_status() -> tuple[HipRuntime, _StatusSink]:
    engine = HipEngine(hip_id="hip-test")
    hb = Heartbeat("hi_p", interval_s=1.0)
    ch = ChangeTracker()
    status = _StatusSink()
    rt = HipRuntime(
        engine=engine,
        hb=hb,
        ch=ch,
        status=status,
        stale_after_ms=500,
        log=logging.getLogger("test.hip_mode_mapping"),
        hip_id="hip-test",
        shadow_mode="old",
    )
    return rt, status


def test_hip_status_mode_uses_core_mode() -> None:
    rt, status = _runtime_with_status()
    rt._last_rx_ns = 0
    rt._last_mode = "IDLE"
    rt._last_estate = "READY"
    rt._last_estop = False
    rt._last_fault = False

    rt._emit_status(now_ns=0)

    assert status.calls
    fields = status.calls[-1]["fields"]
    assert isinstance(fields, dict)
    assert fields.get("mode") == "IDLE"
    assert fields.get("estate") == "READY"
    assert fields.get("armed") is True
    assert fields.get("ready") is True
