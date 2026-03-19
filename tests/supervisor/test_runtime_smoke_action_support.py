from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from steuerung3d.apps.supervisor.actions_transport import UdpDensiActionIn
from steuerung3d.apps.supervisor.runtime_smoke_action_support import (
    bind_smoke_action_input,
    ingest_smoke_actions,
)


def _bool_list() -> list[bool]:
    return []


@dataclass(frozen=True)
class _Action:
    action: str
    value: bool | None = None


@dataclass
class _ActionIn:
    actions: list[_Action]

    def drain_actions(self, limit: int = 1000) -> list[_Action]:
        _ = limit
        drained = list(self.actions)
        self.actions.clear()
        return drained


@dataclass
class _Engine:
    reset_calls: int = 0
    estart_calls: int = 0
    resync_calls: int = 0
    recover_calls: int = 0
    chk_requested: list[bool] = field(default_factory=_bool_list)

    def queue_reset_estop(self) -> None:
        self.reset_calls += 1

    def queue_estart(self) -> None:
        self.estart_calls += 1

    def queue_resync(self) -> None:
        self.resync_calls += 1

    def set_chk_requested(self, checked: bool) -> None:
        self.chk_requested.append(checked)

    def queue_recover(self) -> None:
        self.recover_calls += 1


def test_bind_smoke_action_input_uses_env_and_binder() -> None:
    captured: list[tuple[str, int]] = []

    def _bind(addr: tuple[str, int]) -> Any:
        captured.append(addr)
        return cast(UdpDensiActionIn, object())

    endpoint = bind_smoke_action_input(
        env={"STEUERUNG3D_SUPERVISOR_ACTION_IN": "127.0.0.1:55001"},
        bind_action_in=_bind,
    )

    assert endpoint is not None
    assert captured == [("127.0.0.1", 55001)]


def test_ingest_smoke_actions_dispatches_engine_and_open_hip() -> None:
    engine = _Engine()
    opened: list[str] = []
    action_in = _ActionIn(
        actions=[
            _Action("estop_reset"),
            _Action("estart"),
            _Action("resync"),
            _Action("chk_es_taster", value=True),
            _Action("recover"),
            _Action("open_hip:anton"),
        ]
    )

    def _open_hip(unit_id: str) -> None:
        opened.append(unit_id)

    ingest_smoke_actions(
        smoke_action_in=action_in,
        engine=engine,
        open_hip_for_axis=_open_hip,
    )

    assert engine.reset_calls == 1
    assert engine.estart_calls == 1
    assert engine.resync_calls == 1
    assert engine.chk_requested == [True]
    assert engine.recover_calls == 1
    assert opened == ["anton"]
