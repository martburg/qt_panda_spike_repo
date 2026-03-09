"""Legacy/diagnostic meta helpers for DenSiEngine."""

from __future__ import annotations

from typing import cast

from .engine_host_protocols import DenSiEngineHost


class DenSiMetaMixin:
    def _host(self) -> DenSiEngineHost:
        return cast(DenSiEngineHost, self)

    def step_lifetick(self) -> None:
        """Update legacy device_tick/lifetick meta fields."""
        host = self._host()
        inc_ms = max(1, int(round(host.tb.dt_s * 1000.0)))
        echo_map: dict[str, int] = {}
        if host.last_cmd is not None:
            try:
                echo_map = {
                    str(k): int(v)
                    for k, v in dict(getattr(host.last_cmd, "lifetick_echo", {}) or {}).items()
                }
            except Exception:
                echo_map = {}

        for axis_id, ax in host.state.axes.items():
            prev = int(ax.meta.get("device_tick", 0)) & 0xFFFF
            dev_tick = (prev + inc_ms) & 0xFFFF
            ax.meta["device_tick"] = int(dev_tick)
            ax.meta["lifetick_tx"] = int(dev_tick)
            try:
                ax.meta["lifetick_rx"] = int(echo_map.get(axis_id, 0) or 0)
            except Exception:
                ax.meta["lifetick_rx"] = 0
            ax.meta["timetick_ms"] = int(inc_ms)
