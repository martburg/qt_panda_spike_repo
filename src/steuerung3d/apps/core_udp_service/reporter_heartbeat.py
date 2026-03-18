from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

from steuerung3d.core.core_mode import core_mode_value


class _LogLike(Protocol):
    def info(self, msg: str, *args: object) -> None: ...


class _StateLike(Protocol):
    @property
    def core_mode(self) -> object: ...

    @property
    def rig_mode(self) -> object: ...

    @property
    def estop(self) -> object: ...

    @property
    def fault(self) -> object: ...

    @property
    def axis_claims(self) -> object: ...


def _age(now: float, ts: object) -> float | None:
    if ts is None:
        return None
    try:
        if isinstance(ts, bool):
            return now - float(int(ts))
        if isinstance(ts, (int, float, str)):
            return now - float(ts)
        return None
    except Exception:
        return None


def log_periodic_heartbeat(
    *,
    log: _LogLike,
    now: float,
    t0: float,
    state: _StateLike,
    stats: Mapping[str, int],
    last_seen: Mapping[str, float | None],
) -> bool:
    age_int = _age(now, last_seen.get("intent_ts"))
    age_dev = _age(now, last_seen.get("dev_telem_ts"))
    age_cmd = _age(now, last_seen.get("cmd_ts"))
    age_ui = _age(now, last_seen.get("ui_telem_ts"))
    age_c2 = _age(now, last_seen.get("c2_telem_ts"))

    axis_claims_obj = state.axis_claims
    axis_claims = (
        cast(Mapping[object, object], axis_claims_obj)
        if isinstance(axis_claims_obj, Mapping)
        else {}
    )

    log.info(
        "HB t=%.1fs core_mode=%s rig=%s estop=%s fault=%s claims=%d | intents=%d(age=%s) dev_telem=%d(age=%s) cmd_out=%d(age=%s) ui_telem_out=%d(age=%s) c2_telem_out=%d(age=%s)",
        now - t0,
        core_mode_value(str(state.core_mode or "")),
        str(state.rig_mode or "DISCOVERY"),
        bool(state.estop),
        bool(state.fault),
        len(dict(axis_claims)),
        int(stats.get("intents_in", 0)),
        "n/a" if age_int is None else f"{age_int:.2f}s",
        int(stats.get("dev_telem_in", 0)),
        "n/a" if age_dev is None else f"{age_dev:.2f}s",
        int(stats.get("cmd_out", 0)),
        "n/a" if age_cmd is None else f"{age_cmd:.2f}s",
        int(stats.get("ui_telem_out", 0)),
        "n/a" if age_ui is None else f"{age_ui:.2f}s",
        int(stats.get("c2_telem_out", 0)),
        "n/a" if age_c2 is None else f"{age_c2:.2f}s",
    )
    return True
