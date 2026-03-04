"""Clock + UI-display grace helpers for DenSiEngine.

This module is intentionally small and deterministic in tests via `now_s`.
"""

from __future__ import annotations

from datetime import datetime


class DenSiClockMixin:
    @staticmethod
    def _now_token() -> str:
        """DenSi wallclock token: 'DD-MM-YYYY HH:MM:SS 123 ms'."""
        now = datetime.now()
        ms = int(now.microsecond // 1000)
        return now.strftime("%d-%m-%Y %H:%M:%S ") + f"{ms:03d} ms"

    def within_brake_grace_disp(self) -> bool:
        """UI-display grace helper (monotonic time)."""
        try:
            if self.taster_pressed_s is None:
                return False
            return (float(self.now_s()) - float(self.taster_pressed_s)) < float(
                self.brake_handoff_grace_s
            )
        except Exception:
            return False

    def _update_display_grace_tracking(self) -> None:
        """Update display-only brake grace tracking."""
        try:
            bits = self._ensure_inj_bits()
            taster = bool(bits.get("taster", False))
            if taster and not bool(self.taster_prev_disp):
                self.taster_pressed_s = float(self.now_s())
            if not taster:
                self.taster_pressed_s = None
            self.taster_prev_disp = bool(taster)
        except Exception:
            return
