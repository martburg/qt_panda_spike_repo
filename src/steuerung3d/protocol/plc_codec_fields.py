from __future__ import annotations

# -----------------------------
# Downlink: Controller -> PLC
# -----------------------------
# Token order (matches ST parsing order).
DOWNLINK_BASE_FIELDS = [
    "LifetickUIrx",       # 0
    "Modus",              # 1  (e.g. 'E' normal, 'w' write params)
    "OwnPID",             # 2
    "ControlPIDTx",       # 3
    "Intent",             # 4
    "ControlIN",          # 5
    "GuideControlUI",     # 6
    "SpeedSollIN",        # 7
    "GuideSollSpeedUI",   # 8
    "PosSoll",            # 9
    "EStopReset",         # 10
    "ReSync",             # 11
    "GUINotHaltIN",       # 12
]

DOWNLINK_WRITE_FIELDS = [
    "AccIN",              # 13
    "DccIN",              # 14
    "PosMaxHardUI",       # 15
    "PosMaxUserUI",       # 16
    "PosMinUserUI",       # 17
    "PosMinHardUI",       # 18
    "SpeedMaxUI",         # 19
    "AccMaxUI",           # 20
    "DccMaxUI",           # 21
    "AmpMaxUI",           # 22
    "FilterP",            # 23
    "FilterI",            # 24
    "FilterD",            # 25
    "FilterIL",           # 26
    "GuidePitchUI",       # 27
    "GuidePosMaxUI",      # 28
    "GuidePosMinUI",      # 29
    "VelOrPos",           # 30
    "PosWinUI",           # 31
    "VelWinUI",           # 32
    "AccTotUI",           # 33
]

PARAM_KEYMAP = {
    # internal -> PLC token name (write extension)
    "HardMax": "PosMaxHardUI",
    "UserMax": "PosMaxUserUI",
    "UserMin": "PosMinUserUI",
    "HardMin": "PosMinHardUI",
    "VelMax": "SpeedMaxUI",
    "AccMax": "AccMaxUI",
    "DccMax": "DccMaxUI",
    "MaxAmp": "AmpMaxUI",
    "P": "FilterP",
    "I": "FilterI",
    "D": "FilterD",
    "IL": "FilterIL",
    "Pitch": "GuidePitchUI",
    "PosMax": "GuidePosMaxUI",
    "PosMin": "GuidePosMinUI",
    "PosWin": "PosWinUI",
    "VelWin": "VelWinUI",
    "AccMove": "AccTotUI",
}
