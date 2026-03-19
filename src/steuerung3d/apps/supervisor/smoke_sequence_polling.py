from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar

_T = TypeVar("_T")

_POLL_SLEEP_S = 0.05


def monotonic_deadline(timeout_s: float, *, minimum_s: float = 0.1) -> float:
    return time.monotonic() + max(float(minimum_s), float(timeout_s))


def sleep_until_deadline(deadline: float, delay_s: float) -> None:
    remaining = max(0.0, float(deadline) - time.monotonic())
    delay = min(max(0.0, float(delay_s)), remaining)
    if delay > 0.0:
        time.sleep(delay)


@dataclass(slots=True)
class PublishCadence:
    deadline: float
    interval_s: float
    settle_s: float = 0.0
    start_immediately: bool = True
    next_publish_at: float = field(init=False)

    def __post_init__(self) -> None:
        interval = max(_POLL_SLEEP_S, float(self.interval_s))
        settle = max(0.0, float(self.settle_s))
        object.__setattr__(self, "interval_s", interval)
        object.__setattr__(self, "settle_s", settle)
        start = time.monotonic()
        object.__setattr__(
            self, "next_publish_at", start if self.start_immediately else start + interval
        )

    def maybe_publish(self, publish: Callable[[], None]) -> bool:
        now = time.monotonic()
        if now < self.next_publish_at:
            return False
        publish()
        object.__setattr__(self, "next_publish_at", now + self.interval_s)
        if self.settle_s > 0.0:
            sleep_until_deadline(self.deadline, self.settle_s)
        return True


def poll_until_result(
    *,
    deadline: float,
    check_alive: Callable[[], None],
    observe: Callable[[], _T | None],
    poll_s: float = _POLL_SLEEP_S,
) -> _T | None:
    delay = max(0.0, float(poll_s))
    while time.monotonic() < deadline:
        check_alive()
        result = observe()
        if result is not None:
            return result
        sleep_until_deadline(deadline, delay)
    return None
