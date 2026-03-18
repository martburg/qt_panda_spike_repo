from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from steuerung3d.apps.core_udp_service.reporter import emit_birds_eye_status, log_periodic_heartbeat


class _Status:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def emit_every(self, *, level: str, summary: str, fields: dict[str, object]) -> None:  # noqa: D401
        self.calls.append((level, summary, fields))


@dataclass
class _Snap:
    tick: int = 1
    estop: bool = False
    fault: bool = False
    core_mode: str = ""
    estop_status_word: int = 0
    densis: Mapping[str, object] = field(default_factory=lambda: {})


class _State:
    core_mode = ""
    rig_mode = "DISCOVERY"
    estop = False
    fault = False
    axis_claims: dict[str, str] = {}
    core_blocked_by: list[object] = []
    core_motion_allowed: bool = False
    axis_cmd: dict[str, object] = {}
    core_axis_gate: dict[str, dict[str, object]] = {}
    lease_axis_holders: dict[str, list[str]] = {}
    estop_reset_denied_count_by_axis: dict[str, int] = {}
    joy = None

    def claim_owner(self, axis_id: str) -> str:
        return ""


class _Router:
    last_dev_estop_word_by_axis: dict[str, int] = {}


def test_reporter_exports_and_birds_eye_is_best_effort() -> None:
    status = _Status()
    snap = _Snap(densis={"Anton": {}, "Debby": {}})
    state = _State()
    router = _Router()

    emit_birds_eye_status(
        status=status,
        snap=snap,
        state=state,
        router=router,
        axis_ids=["Anton"],
        last_intents_meta={"count": 0, "types": []},
        last_seen={
            "intent_ts": None,
            "dev_telem_ts": None,
            "cmd_ts": None,
            "ui_telem_ts": None,
            "c2_telem_ts": None,
        },
    )

    assert status.calls, "Expected at least one birds-eye emission"
    level, summary, fields = status.calls[-1]
    assert level in {"OK", "WARN", "ERR"}
    assert "component" in fields and fields["component"] == "core"
    assert "axes" in fields and isinstance(fields["axes"], list)
    assert "devices" in fields and isinstance(fields["devices"], list)
    assert "core_mode" in fields
    assert isinstance(summary, str)


def test_log_periodic_heartbeat_smoke() -> None:
    class _Log:
        def __init__(self) -> None:
            self.msgs: list[str] = []

        def info(self, msg: str, *args: object) -> None:
            self.msgs.append(msg % args)

    log = _Log()
    ok = log_periodic_heartbeat(
        log=cast(Any, log),
        now=10.0,
        t0=0.0,
        state=cast(Any, _State()),
        stats={
            "intents_in": 0,
            "dev_telem_in": 0,
            "cmd_out": 0,
            "ui_telem_out": 0,
            "c2_telem_out": 0,
        },
        last_seen={
            "intent_ts": None,
            "dev_telem_ts": None,
            "cmd_ts": None,
            "ui_telem_ts": None,
            "c2_telem_ts": None,
        },
    )
    assert ok is True
    assert log.msgs
