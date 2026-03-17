"""Small controller helpers shared by Yellow controllers.

Typing note:
These helpers are used by multiple Qt controllers and are intentionally tiny.
We keep the runtime surface unchanged, but provide concrete types so Pyright can
reason about observability objects and Qt timer parenting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, TypeVar

from PySide6.QtCore import QObject, QTimer

from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat, RateLimiter


class StatusEmitterLike(Protocol):
    """Minimal interface of the optional structured status emitter."""

    @classmethod
    def from_env(cls, *, default_service: str) -> "StatusEmitterLike": ...

    def emit_every(self, *, level: str, summary: str, fields: dict[str, object]) -> None: ...


@dataclass(slots=True)
class GuardedControllerOps:
    """Tiny keyed wrappers for swallowed controller-side soft errors.

    This keeps controller orchestration code readable while preserving the
    existing best-effort semantics used around binder/UI interactions.
    """

    soft_errors: dict[str, int]

    def bump(self, key: str) -> None:
        bump_soft_error(self.soft_errors, key)

    def best_effort(self, key: str, func: Callable[[], None]) -> None:
        best_effort(func, on_error=lambda: self.bump(key))

    def read_or_fallback(self, key: str, func: Callable[[], _T], *, fallback: _T) -> _T:
        return read_or_fallback(func, fallback=fallback, on_error=lambda: self.bump(key))


def init_observability(
    service_name: str,
    *,
    status_emitter_cls: type[StatusEmitterLike] | None,
    status_default_service: str,
    dbg_rl_interval_s: float | None = None,
) -> tuple[Heartbeat, ChangeTracker, StatusEmitterLike | None, RateLimiter | None]:
    hb = Heartbeat(str(service_name or ""), interval_s=1.0)
    ch = ChangeTracker()
    status = (
        status_emitter_cls.from_env(default_service=status_default_service)
        if status_emitter_cls
        else None
    )
    dbg_rl = RateLimiter(float(dbg_rl_interval_s)) if dbg_rl_interval_s is not None else None
    return hb, ch, status, dbg_rl


def start_poll_timer(win: QObject, *, period_ms: int, callback: Callable[[], None]) -> QTimer:
    t = QTimer(win)
    t.setInterval(int(period_ms))
    t.timeout.connect(callback)
    t.start()
    return t


_T = TypeVar("_T")


def run_guarded(func: Callable[[], None], *, on_error: Callable[[], None] | None = None) -> None:
    if on_error is None:
        func()
        return
    try:
        func()
    except Exception:
        on_error()


def read_or_fallback(
    func: Callable[[], _T],
    *,
    fallback: _T,
    on_error: Callable[[], None] | None = None,
) -> _T:
    try:
        return func()
    except Exception:
        if on_error is not None:
            on_error()
        return fallback


def best_effort(
    func: Callable[[], None],
    *,
    on_error: Callable[[], None] | None = None,
) -> None:
    try:
        func()
    except Exception:
        if on_error is not None:
            on_error()


def bump_soft_error(counters: dict[str, int], key: str) -> None:
    counters[str(key)] = int(counters.get(str(key), 0)) + 1
