"""Clock + UI-display grace helpers for DenSiEngine.

This module is intentionally small and deterministic in tests via `now_s`.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

from .engine_host_protocols import DenSiEngineHost


class DenSiClockMixin:
    def _host(self) -> DenSiEngineHost:
        return cast(DenSiEngineHost, self)

    @staticmethod
    def _now_token() -> str:
        """DenSi wallclock token: 'DD-MM-YYYY HH:MM:SS 123 ms'."""
        now = datetime.now()
        ms = int(now.microsecond // 1000)
        return now.strftime("%d-%m-%Y %H:%M:%S ") + f"{ms:03d} ms"

    def within_brake_grace_disp(self) -> bool:
        """UI-display grace helper (monotonic time)."""
        host = self._host()
        try:
            if host.taster_pressed_s is None:
                return False
            return (float(host.now_s()) - float(host.taster_pressed_s)) < float(
                host.brake_handoff_grace_s
            )
        except Exception:
            return False

    def _update_display_grace_tracking(self) -> None:
        """Update display-only brake grace tracking."""
        host = self._host()
        try:
            bits = host._ensure_inj_bits()
            taster = bool(bits.get("taster", False))
            if taster and not bool(host.taster_prev_disp):
                host.taster_pressed_s = float(host.now_s())
            if not taster:
                host.taster_pressed_s = None
            host.taster_prev_disp = bool(taster)
        except Exception:
            return
