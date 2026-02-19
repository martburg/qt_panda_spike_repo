"""Shared runtime helpers (Qt-free)."""

from __future__ import annotations

import logging
from typing import Mapping, Any

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
