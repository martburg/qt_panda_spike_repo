"""Shared runtime helpers (Qt-free).

Keep this module *boringly mechanical*.

REFOS note:
- Lane 1 only: helpers that reduce duplication without changing runtime semantics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from steuerung3d.util.ratelimit import rl_log_exc


def compute_age_ms(now_ns: int, last_ns: int | None) -> float | None:
    if last_ns is None:
        return None
    return (int(now_ns) - int(last_ns)) / 1_000_000.0


def format_age_ms(age_ms: float | None) -> str:
    return "NA" if age_ms is None else f"{age_ms:.0f}"


def compute_stale(age_ms: float | None, stale_after_ms: int) -> bool:
    return (age_ms is None) or (float(age_ms) >= float(stale_after_ms))


def compute_status_level(estop: bool, fault: bool, stale: bool) -> str:
    if estop or fault:
        return "ERR"
    if stale:
        return "WARN"
    return "OK"


def emit_status(
    status,
    *,
    level: str,
    summary: str,
    fields: Mapping[str, Any],
    log: logging.Logger,
    exc_tag: str,
    exc_msg: str,
) -> None:
    try:
        status.emit_every(level=level, summary=summary, fields=dict(fields))
    except Exception:
        rl_log_exc(str(exc_tag), str(exc_msg), logger=log)


@dataclass(frozen=True)
class RuntimeHealth:
    """Common derived health fields for status/heartbeat emission."""

    age_ms: float | None
    stale: bool
    level: str
    online: bool
    age_disp: str


def compute_runtime_health(
    *,
    now_ns: int,
    last_rx_ns: int | None,
    stale_after_ms: int,
    seen_first_rx: bool,
    estop: bool,
    fault: bool,
) -> RuntimeHealth:
    """Compute common health fields.

    This keeps the *definition* of "stale/online/level" consistent across runtimes,
    while each runtime decides what to do with these fields.
    """

    age_ms = compute_age_ms(int(now_ns), last_rx_ns)
    stale = compute_stale(age_ms, int(stale_after_ms))
    level = compute_status_level(bool(estop), bool(fault), bool(stale))
    online = bool(seen_first_rx) and (not bool(stale))
    age_disp = format_age_ms(age_ms)
    return RuntimeHealth(age_ms=age_ms, stale=stale, level=level, online=online, age_disp=age_disp)


def should_interval_log(now_s: float, last_log_s: float, *, interval_s: float = 1.0) -> bool:
    """Return True when a log line should be emitted based on an interval.

    Intentionally tolerant of bad values; prefer logging over silence.
    """
    try:
        return (float(now_s) - float(last_log_s)) >= float(interval_s)
    except Exception:
        return True
