from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from steuerung3d.core.telemetry import TelemetrySnapshot

from .axis_router_snapshot import fanout_snapshot_with_axis_caches, slice_snapshot_for_axis

if TYPE_CHECKING:
    from .axis_router import AxisRouter


def publish_ui_snapshot(router: "AxisRouter", snap: TelemetrySnapshot) -> int:
    sent = 0
    if router.ui_telem_fanout:
        fanout_snap = fanout_snapshot_with_axis_caches(router, snap)
        diag_log = logging.getLogger("axis_router")
        densis_dbg: dict[str, dict[str, str | bool]] = {}
        for k, d in dict(getattr(fanout_snap, "densis", {}) or {}).items():
            densis_dbg[str(k)] = {
                "online": bool(getattr(d, "online", False)),
                "owner": str(getattr(d, "claimed_by_hip", "") or ""),
            }
        for tx in router.ui_telem_fanout:
            target = getattr(getattr(getattr(tx, "tx", None), "link", None), "target", None)
            diag_log.info(
                "ui fanout tx target=%s tick=%s core_mode=%s estop=%s fault=%s densis=%s",
                target,
                getattr(fanout_snap, "tick", None),
                getattr(fanout_snap, "core_mode", None),
                getattr(fanout_snap, "estop", None),
                getattr(fanout_snap, "fault", None),
                densis_dbg,
            )
            tx.publish_telemetry(fanout_snap)
            sent += 1
        return sent

    for axis_id in router.axis_ids:
        tx = router.ui_telem_out_by_axis.get(axis_id)
        if tx is None:
            continue
        tx.publish_telemetry(slice_snapshot_for_axis(router, snap, axis_id))
        sent += 1
    return sent
