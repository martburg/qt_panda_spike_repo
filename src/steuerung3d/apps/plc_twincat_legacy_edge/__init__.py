"""Edge adapter process for TwinCAT legacy PLC UDP protocol.

This module is kept for field rigs / reference. New development should prefer the
schema-driven PLC adapter under ``steuerung3d.adapters.plc``.
"""

OBSOLETE = True
OBSOLETE_REASON = "Legacy TwinCAT UDP edge adapter; prefer schema-driven PLC adapter + StackSpec profiles."

import warnings

warnings.warn(
    f"{__name__} is obsolete: {OBSOLETE_REASON}",
    category=UserWarning,
    stacklevel=2,
)
