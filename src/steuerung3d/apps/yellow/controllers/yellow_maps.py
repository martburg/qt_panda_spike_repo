from __future__ import annotations

"""Shared UI widget name maps for Yellow (HiP / DenSi).

Keep these centralized to avoid drift between controllers.

- PARAM_WIDGETS maps param keys to the corresponding QLineEdit objectName in the UI.
- LIMIT_WIDGETS maps limit keys to compact header limit fields.
"""

# v0.1 axis-agnostic parameter wiring (UI widget names -> param keys)
PARAM_WIDGETS: dict[str, dict[str, str]] = {
    "pos": {
        "HardMax": "txtHardMax_2",
        "UserMax": "txtUserMax_2",
        "UserMin": "txtUserMin_2",
        "HardMin": "txtHardMin_2",
        "PosWin": "txtPosWin_2",
    },
    "vel": {
        "VelMax": "txtVelMax_3",
        "VelWin": "txtVelWin_3",
        "AccMax": "txtAccMax_3",
        "AccMove": "txtAccMove_3",
        "DccMax": "txtDccMax_3",
        "MaxAmp": "txtMaxAmp_3",
        "VelMaxMot": "txtVelMaxMot_3",
    },
    "filter": {
        "P": "txtP_2",
        "I": "txtI_2",
        "D": "txtD_2",
        "IL": "txtIL_2",
        "RampForm": "txtRamp_2",
    },
    "guider": {
        "PosMin": "txtGPosMin_3",
        "PosMax": "txtGPosMax_2",
        "Pitch": "txtPitch_2",
    },
}

# Limit display fields in the header bar (meters)
LIMIT_WIDGETS: dict[str, str] = {
    "HardMin": "txtLimitHardMin",
    "UserMin": "txtLimitUserMin",
    "UserMax": "txtLimitUserMax",
    "HardMax": "txtLimitHardMax",
}
