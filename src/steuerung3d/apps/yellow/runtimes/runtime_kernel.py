"""Shared helpers for Yellow runtimes.

This is intentionally small and boring:
- avoid copy/paste of status emission patterns
- keep runtime_impl modules focused on their engine wiring

Lane 1 note: this is a structural refactor only.
"""

from __future__ import annotations

from typing import Any, Mapping

from .runtime_utils import compute_runtime_health, emit_status


def compute_health(
    *,
    now_ns: int,
    last_rx_ns: int | None,
    stale_after_ms: int,
    seen_first_rx: bool,
    estop: bool,
    fault: bool,
):
    """Compute health for a runtime stream (telemetry or commands)."""
    return compute_runtime_health(
        now_ns=int(now_ns),
        last_rx_ns=last_rx_ns,
        stale_after_ms=int(stale_after_ms),
        seen_first_rx=bool(seen_first_rx),
        estop=bool(estop),
        fault=bool(fault),
    )


def with_health_fields(
    base_fields: Mapping[str, Any],
    *,
    health,
    estop: bool,
    fault: bool,
) -> dict[str, Any]:
    """Merge standard health fields into a status payload."""
    age_ms = getattr(health, "age_ms", None)
    stale = bool(getattr(health, "stale", False))
    return {
        **dict(base_fields),
        "age_ms": (-1 if age_ms is None else float(age_ms)),
        "stale": bool(stale),
        "estop": bool(estop),
        "fault": bool(fault),
    }


def emit_runtime_status(
    status,
    *,
    level: str,
    summary: str,
    fields: Mapping[str, Any],
    log,
    exc_tag: str,
    exc_msg: str,
) -> None:
    """Best-effort status emission wrapper."""
    emit_status(
        status,
        level=str(level),
        summary=str(summary),
        fields=dict(fields),
        log=log,
        exc_tag=str(exc_tag),
        exc_msg=str(exc_msg),
    )
