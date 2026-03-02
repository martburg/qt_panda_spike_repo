from __future__ import annotations

"""steuerung3d.util.ratelimit

Rate-limited logging helpers.

Why this exists:
- UI/controller loops must never die on exceptions.
- But swallowing exceptions silently makes semantic/UI regressions hard to see.
- Plain log.exception(...) in a fast loop can spam logs and hurt responsiveness.

This module provides a tiny per-key rate limiter and a convenience helper to log
exceptions at a controlled frequency (default: once per 2 seconds per key).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict


@dataclass
class RateLimiter:
    """Allow an event only once per `min_interval_s` per key."""

    min_interval_s: float = 2.0
    _last_s: Dict[str, float] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        last = self._last_s.get(key, -1.0e30)
        if (now - last) < float(self.min_interval_s):
            return False
        self._last_s[key] = now
        return True


_rl = RateLimiter()


def rl_log_exc(
    key: str,
    message: str,
    *,
    logger: logging.Logger | None = None,
    level: str = "debug",
) -> None:
    """Log the current exception (exc_info=True) at most once per key per interval."""
    log = logger or logging.getLogger(__name__)
    if not _rl.allow(key):
        return
    fn: Callable[..., object] = getattr(log, level, log.debug)
    fn(message, exc_info=True)
