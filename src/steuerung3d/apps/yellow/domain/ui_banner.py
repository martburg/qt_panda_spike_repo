# src/steuerung3d/apps/yellow/domain/ui_banner.py
"""Shared banner helpers (E-Stop ladder estate).

Both HiP and DenSi show the same compact *SafetyPLC ladder estate* banner:

  ESTOP  IDLE  ARMED  READY

The banner is derived *only* from the Safety PLC's EStopStatus word.
We keep the mapping logic here so the controllers stay readable.

Notes
-----
The ladder has a special case for brakes:

- When the deadman (taster) is pressed, brake feedback can legitimately lag
  for a short grace window. During that grace window we do **not** treat the
  brake bits as a trip cause.

Callers provide `within_brake_grace()` to encode that policy.
"""

from __future__ import annotations

from .banner_facts import BANNER_DYNAMIC_EXCLUDE, derive_banner_estate_from_word


# --- UI styling ---------------------------------------------------------------

BANNER_COLORS: dict[str, tuple[str, str]] = {
    "ESTOP": ("#F9E547", "#000000"),  # yellow
    "IDLE": ("#FFB300", "#000000"),  # amber
    "ARMED": ("#1B5E20", "#FFFFFF"),  # dark green
    "READY": ("#2E7D32", "#FFFFFF"),  # green
}


