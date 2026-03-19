from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from steuerung3d.core.net import parse_hostport
from steuerung3d.protocol.udp_channels import close_udp_json_endpoint

from .actions_transport import UdpDensiActionIn

log = logging.getLogger("supervisor")


class _SmokeActionLike(Protocol):
    @property
    def action(self) -> str: ...

    @property
    def value(self) -> bool | None: ...


class _SmokeActionInLike(Protocol):
    def drain_actions(self, limit: int = 1000) -> Sequence[_SmokeActionLike]: ...


class _EngineSmokeActionSink(Protocol):
    def queue_reset_estop(self) -> None: ...

    def queue_estart(self) -> None: ...

    def queue_resync(self) -> None: ...

    def set_chk_requested(self, checked: bool) -> None: ...

    def queue_recover(self) -> None: ...


SmokeActionBinder = Callable[[tuple[str, int]], UdpDensiActionIn]
SmokeActionOpener = Callable[[str], None]


def bind_smoke_action_input(
    *,
    env: Mapping[str, str] | None = None,
    bind_action_in: SmokeActionBinder | None = None,
) -> UdpDensiActionIn | None:
    environ = env if env is not None else os.environ
    smoke_action_in_addr = str(environ.get("STEUERUNG3D_SUPERVISOR_ACTION_IN", "") or "").strip()
    if not smoke_action_in_addr:
        return None
    binder = bind_action_in if bind_action_in is not None else UdpDensiActionIn.bind
    try:
        return binder(parse_hostport(smoke_action_in_addr))
    except Exception:
        log.exception("failed to bind supervisor smoke action input %s", smoke_action_in_addr)
        return None


def ingest_smoke_actions(
    *,
    smoke_action_in: _SmokeActionInLike | None,
    engine: _EngineSmokeActionSink,
    open_hip_for_axis: SmokeActionOpener,
) -> None:
    if smoke_action_in is None:
        return
    try:
        actions = list(smoke_action_in.drain_actions(limit=100) or [])
    except Exception:
        log.exception("failed to drain supervisor smoke actions")
        return
    for action in actions:
        dispatch_smoke_action(
            action=action,
            engine=engine,
            open_hip_for_axis=open_hip_for_axis,
        )


def dispatch_smoke_action(
    *,
    action: _SmokeActionLike,
    engine: _EngineSmokeActionSink,
    open_hip_for_axis: SmokeActionOpener,
) -> None:
    name = str(getattr(action, "action", "") or "")
    if name == "estop_reset":
        engine.queue_reset_estop()
    elif name == "estart":
        engine.queue_estart()
    elif name == "resync":
        engine.queue_resync()
    elif name == "chk_es_taster":
        engine.set_chk_requested(bool(getattr(action, "value", False)))
    elif name == "recover":
        engine.queue_recover()
    elif name.startswith("open_hip:"):
        open_hip_for_axis(name.split(":", 1)[1])


def close_smoke_action_input(smoke_action_in: object | None) -> None:
    if smoke_action_in is None:
        return
    close_udp_json_endpoint(smoke_action_in)
