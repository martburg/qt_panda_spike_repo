# src/steuerung3d/apps/yellow/controllers/ui_estop.py
"""Shared UI decision helpers for E-Stop / header dots.

Goal
----
Keep HiP and DenSi controllers readable by moving repeated *decision logic*
into small, testable helpers.

These helpers deliberately do NOT know about particular windows or widget trees.
They only compute *what state a dot should show* based on decoded E-Stop bits
and caller-provided policies (e.g. brake dot equivalence logic).

Dot state convention (used by QSS)
----------------------------------
- "good" : green / OK
- "warn" : amber / attention
- "bad"  : red / fault
- None   : off / not applicable
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from steuerung3d.protocol.estop_bits import ESTOP_CAUSE_KEYS as _ESTOP_CAUSE_KEYS
from steuerung3d.protocol.estop_bits import ESTOP_OK_KEYS as _ESTOP_OK_KEYS


@dataclass(frozen=True)
class DotSpec:
    """Minimal shape of the estop bit specs we care about.

    We accept the real EstopBitSpec from `steuerung3d.protocol.estop_bits` but
    keep this tiny adapter so unit tests can exercise the logic without importing
    the whole protocol module.
    """
    key: str
    dot: str | None = None


def compute_estop_dot_state(
    *,
    key: str,
    value: bool,
    taster: bool,
    brake_ok_display: Callable[[bool], bool] | None,
    cause_keys: set[str] | None,
    ok_keys: set[str] | None,
) -> str | None:
    """Compute the UI state for one E-Stop dot.

    This matches the *legacy semantic buckets* used in both HiP and DenSi:

    - brk1_ok / brk2_ok: shown as green/red using brake-display policy
    - brk2kb_ok: cable OK uses raw bit
    - trip causes: red when active, otherwise green
    - OK chain: green when OK, red when broken
    - everything else: amber only when asserted, otherwise off
    """

    if key in ("brk1_ok", "brk2_ok") and brake_ok_display is not None:
        disp_ok = bool(brake_ok_display(value))
        return "good" if disp_ok else "bad"

    if key == "brk2kb_ok":
        return "good" if value else "bad"

    ck = _ESTOP_CAUSE_KEYS if cause_keys is None else cause_keys
    ok = _ESTOP_OK_KEYS if ok_keys is None else ok_keys

    if key in ck:
        return "bad" if value else "good"

    if key in ok:
        return "good" if value else "bad"

    return "warn" if value else None


def compute_estop_dot_states(
    *,
    bits: dict[str, bool],
    taster: bool,
    specs: Iterable[Any],
    brake_ok_display: Callable[[bool], bool] | None,
    cause_keys: set[str] | None = None,
    ok_keys: set[str] | None = None,
) -> dict[str, str | None]:
    """Compute dot states for all E-Stop-related dots from decoded bits."""

    out: dict[str, str | None] = {}
    for spec in specs:
        dot = getattr(spec, "dot", None)
        key = str(getattr(spec, "key", ""))
        if not dot or not key:
            continue
        v = bool(bits.get(key, False))
        out[str(dot)] = compute_estop_dot_state(
            key=key,
            value=v,
            taster=taster,
            brake_ok_display=brake_ok_display,
            cause_keys=cause_keys,
            ok_keys=ok_keys,
        )
    return out


def compute_header_estop_dot_states(
    *,
    taster: bool,
    ready: bool,
    brk1_raw: bool,
    brk2_raw: bool,
    brake_ok_display: Callable[[bool], bool],
) -> dict[str, str]:
    """Compute header dots that are derived from E-Stop chain bits.

    The header dots are always present (if the UI has them) and use a compact
    rule set:
      - FBT (taster): green when pressed, amber otherwise
      - READY: green when ready, amber otherwise
      - BRAKE1/BRAKE2: green when brake display says OK, red otherwise
    """
    brk1_ok = bool(brake_ok_display(brk1_raw))
    brk2_ok = bool(brake_ok_display(brk2_raw))
    return {
        "dotHdrFbt": "good" if taster else "warn",
        "dotHdrReady": "good" if ready else "warn",
        "dotHdrBrake1": "good" if brk1_ok else "bad",
        "dotHdrBrake2": "good" if brk2_ok else "bad",
    }


def age_to_online_state(
    *,
    age: float,
    good_max: float,
    warn_max: float | None = None,
) -> str:
    """Map a monotonically increasing age metric to a traffic/online dot state.

    `age` can be seconds, ticks, or any increasing unit. Callers choose thresholds.

    - <= good_max  -> green
    - <= warn_max  -> amber
    - otherwise    -> red

    If `warn_max` is None, we never return red; anything above good_max is amber.
    """
    if age <= good_max:
        return "good"
    if warn_max is None:
        return "warn"
    return "warn" if age <= warn_max else "bad"
