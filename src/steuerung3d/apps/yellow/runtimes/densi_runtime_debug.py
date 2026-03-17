from __future__ import annotations

import time

from steuerung3d.core.command_frame import CommandFrame

from .densi_runtime_types import DensiRuntimeDebugLike
from .runtime_utils import should_interval_log


def step_lifetick_debug(
    rt: DensiRuntimeDebugLike, *, now_ns: int, last_cmd: CommandFrame | None
) -> None:
    now_s = time.monotonic()
    echo_map = getattr(last_cmd, "lifetick_echo", {}) if last_cmd is not None else {}

    if last_cmd is not None and rt._axis_ids:
        for axis_id in rt._axis_ids:
            echo_val = dict(echo_map).get(axis_id, None)
            prev = rt._lt_last_echo_by_axis.get(axis_id)
            if prev != echo_val:
                rt._lt_last_echo_by_axis[axis_id] = echo_val
                rt._log.debug(
                    "LIFETICK DenSi rx cmd echo: axis=%s value=%s cmd_tick=%s",
                    axis_id,
                    echo_val,
                    getattr(last_cmd, "tick", None),
                )

        if should_interval_log(now_s, rt._lt_last_cmd_log_s):
            axis0 = rt._axis_ids[0]
            rt._log.debug(
                "DenSi rx cmd: tick=%s lifetick_echo[%s]=%s (map=%s)",
                getattr(last_cmd, "tick", None),
                axis0,
                dict(echo_map).get(axis0, None),
                echo_map,
            )
            rt._lt_last_cmd_log_s = now_s
    else:
        if should_interval_log(now_s, rt._lt_last_cmd_log_s):
            rt._log.debug("DenSi rx cmd: <no cmd yet>")
            rt._lt_last_cmd_log_s = now_s

    for axis_id, ax in rt.engine.state.axes.items():
        tx = int(ax.meta.get("lifetick_tx", 0) or 0) & 0xFFFF
        rx = int(ax.meta.get("lifetick_rx", 0) or 0) & 0xFFFF
        diff = (tx - rx) & 0xFFFF

        if rt._axis_ids and axis_id == rt._axis_ids[0]:
            rt._hb.set("tx", int(tx))
            rt._hb.set("rx", int(rx))
            rt._hb.set("diff", int(diff))
            if rt._last_cmd_ns is not None:
                rt._hb.set("cmd_age_ms", int((int(now_ns) - int(rt._last_cmd_ns)) / 1_000_000.0))

        if (
            rt._axis_ids
            and axis_id == rt._axis_ids[0]
            and should_interval_log(now_s, rt._lt_last_telem_log_s)
        ):
            rt._lt_last_telem_log_s = now_s
            rt._log.debug(
                "LIFETICK DenSi device: axis=%s tx=%d rx=%d diff=%d",
                axis_id,
                tx,
                rx,
                diff,
            )
