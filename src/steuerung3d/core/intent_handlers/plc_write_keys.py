from __future__ import annotations

# PLC Modus 'w' expects the full parameter set on each write.
# We merge partial UI writes with last-known params to avoid zeroing untouched fields.
PLC_WRITE_KEYS = {
    "HardMax",
    "UserMax",
    "UserMin",
    "HardMin",
    "VelMax",
    "AccMax",
    "DccMax",
    "MaxAmp",
    "P",
    "I",
    "D",
    "IL",
    "RampForm",
    "Pitch",
    "PosMax",
    "PosMin",
    "PosWin",
    "VelWin",
    "AccMove",
    "VelMaxMot",
}
