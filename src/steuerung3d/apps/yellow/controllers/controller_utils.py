"""Small controller helpers shared by Yellow controllers."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QTimer

from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat, RateLimiter


def init_observability(
    service_name: str,
    *,
    status_emitter_cls,
    status_default_service: str,
    dbg_rl_interval_s: float | None = None,
) -> tuple[Heartbeat, ChangeTracker, object | None, RateLimiter | None]:
    hb = Heartbeat(str(service_name or ""), interval_s=1.0)
    ch = ChangeTracker()
    status = (
        status_emitter_cls.from_env(default_service=status_default_service)
        if status_emitter_cls
        else None
    )
    dbg_rl = RateLimiter(float(dbg_rl_interval_s)) if dbg_rl_interval_s is not None else None
    return hb, ch, status, dbg_rl


def start_poll_timer(win, *, period_ms: int, callback: Callable[[], None]) -> QTimer:
    t = QTimer(win)
    t.setInterval(int(period_ms))
    t.timeout.connect(callback)
    t.start()
    return t


def run_guarded(func: Callable[[], None], *, on_error: Callable[[], None] | None = None) -> None:
    if on_error is None:
        func()
        return
    try:
        func()
    except Exception:
        on_error()
