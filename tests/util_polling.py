from __future__ import annotations

import time
from collections.abc import Callable


def poll_until(
    predicate: Callable[[], bool],
    *,
    timeout_s: float = 2.0,
    interval_s: float = 0.01,
) -> bool:
    """Poll `predicate` until it returns True or timeout expires.

    Useful for avoiding fixed sleeps in integration-ish tests.
    """

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return bool(predicate())
