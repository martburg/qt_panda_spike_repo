"""Legacy TwinCAT PLC-facing adapters (real PLC or PLC simulator).

The TwinCAT legacy protocol uses semicolon-separated fields and has multiple
install-specific variants.

Status:
- **Obsolete** for new development.
- Kept to support older rigs and as a reference implementation.

Prefer:
- ``steuerung3d.adapters.plc`` (schema-driven codec + early UDP device)
"""

OBSOLETE = True
OBSOLETE_REASON = "Legacy TwinCAT adapter; prefer schema-driven PLC adapter (steuerung3d.adapters.plc)."

import warnings

warnings.warn(
    f"{__name__} is obsolete: {OBSOLETE_REASON}",
    category=UserWarning,
    stacklevel=2,
)
