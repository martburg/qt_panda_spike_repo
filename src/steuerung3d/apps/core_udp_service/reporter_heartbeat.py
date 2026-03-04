from __future__ import annotations

from steuerung3d.core.core_mode import core_mode_value


def log_periodic_heartbeat(*, log, now: float, t0: float, state, stats, last_seen) -> bool:
    age_int = None if last_seen["intent_ts"] is None else now - last_seen["intent_ts"]
    age_dev = None if last_seen["dev_telem_ts"] is None else now - last_seen["dev_telem_ts"]
    age_cmd = None if last_seen["cmd_ts"] is None else now - last_seen["cmd_ts"]
    age_ui = None if last_seen["ui_telem_ts"] is None else now - last_seen["ui_telem_ts"]
    age_c2 = None if last_seen["c2_telem_ts"] is None else now - last_seen["c2_telem_ts"]

    log.info(
        "HB t=%.1fs core_mode=%s rig=%s estop=%s fault=%s claims=%d | intents=%d(age=%s) dev_telem=%d(age=%s) cmd_out=%d(age=%s) ui_telem_out=%d(age=%s) c2_telem_out=%d(age=%s)",
        now - t0,
        core_mode_value(getattr(state, "core_mode", "")),
        getattr(state, "rig_mode", "DISCOVERY"),
        bool(getattr(state, "estop", False)),
        bool(getattr(state, "fault", False)),
        len(dict(getattr(state, "axis_claims", {}) or {})),
        stats["intents_in"],
        "n/a" if age_int is None else f"{age_int:.2f}s",
        stats["dev_telem_in"],
        "n/a" if age_dev is None else f"{age_dev:.2f}s",
        stats["cmd_out"],
        "n/a" if age_cmd is None else f"{age_cmd:.2f}s",
        stats["ui_telem_out"],
        "n/a" if age_ui is None else f"{age_ui:.2f}s",
        stats["c2_telem_out"],
        "n/a" if age_c2 is None else f"{age_c2:.2f}s",
    )
    return True
