"""Lightweight logging helpers for multi-process stacks.

Goal: make it easy to add *useful* logs without spamming or changing runtime
behavior.

Design principles
-----------------
- **Heartbeats**: one INFO line every N seconds summarizing "what's going on".
- **Edge logs**: when a state value changes (mode/estop/selection/online).
- **Throttled traces**: noisy per-tick signals stay at DEBUG and are rate-limited.

These helpers are intentionally dependency-free (stdlib only).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


def _now_s() -> float:
    return time.monotonic()


@dataclass
class RateLimiter:
    """Allow an action at most once per interval."""

    interval_s: float
    last_s: float = 0.0

    def due(self, now_s: float | None = None) -> bool:
        now = _now_s() if now_s is None else float(now_s)
        return (now - float(self.last_s)) >= float(self.interval_s)

    def mark(self, now_s: float | None = None) -> None:
        self.last_s = _now_s() if now_s is None else float(now_s)


@dataclass
class Heartbeat:
    """Accumulate counters/fields and emit a periodic summary log."""

    name: str
    interval_s: float = 1.0
    last_emit_s: float = field(default_factory=_now_s)
    counters: Dict[str, int] = field(default_factory=dict)
    fields: Dict[str, Any] = field(default_factory=dict)

    def inc(self, key: str, n: int = 1) -> None:
        self.counters[key] = int(self.counters.get(key, 0)) + int(n)

    def set(self, key: str, value: Any) -> None:
        self.fields[key] = value

    def due(self, now_s: float | None = None) -> bool:
        now = _now_s() if now_s is None else float(now_s)
        return (now - float(self.last_emit_s)) >= float(self.interval_s)

    def emit(self, log, *, level: str = "info", now_s: float | None = None, reset: bool = True) -> None:
        """Emit a single summary line if due.

        The caller is responsible for choosing the logger. `level` is one of
        info/debug/warning/error.
        """
        now = _now_s() if now_s is None else float(now_s)
        if not self.due(now):
            return
        self.last_emit_s = now

        parts: list[str] = [self.name]
        if self.fields:
            parts.append("fields=" + _fmt_kv(self.fields))
        if self.counters:
            parts.append("counts=" + _fmt_kv(self.counters))
        msg = " | ".join(parts)

        fn = getattr(log, level, None)
        if callable(fn):
            fn(msg)
        else:
            log.info(msg)

        if reset:
            self.counters.clear()


@dataclass
class ChangeTracker:
    """Track last values and report changes."""

    last: Dict[str, Any] = field(default_factory=dict)

    def changed(self, key: str, value: Any) -> bool:
        prev = self.last.get(key, object())
        if prev != value:
            self.last[key] = value
            return True
        return False


def _fmt_kv(m: Mapping[str, Any]) -> str:
    items = []
    for k, v in m.items():
        try:
            items.append(f"{k}={v}")
        except Exception:
            items.append(f"{k}=<?> ")
    return ",".join(items)
