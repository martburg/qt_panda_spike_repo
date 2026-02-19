"""DenSi E-Stop 'taster edge' tracking (Qt-free).

Compatibility re-export from the shared domain helper.
"""

from __future__ import annotations

from ...domain.taster_edge_state import TasterEdgeState, update_taster_edge_state, within_brake_grace

__all__ = ["TasterEdgeState", "update_taster_edge_state", "within_brake_grace"]
