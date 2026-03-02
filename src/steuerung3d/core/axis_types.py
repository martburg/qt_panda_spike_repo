from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AxisTelemetry:
    # ---- link / identity ----
    link_ok: bool
    name: str
    own_pid_rx: str  # uplink field 0 (PLC's "OwnPID" echo)
    lifetick_tx: int  # uplink field 1 (PLC LifetickUItx)
    status_word: int  # uplink field 2
    guide_status_word: int  # uplink field 3
    estop_status_dword: int  # uplink field 37
    system_time: str = ""  # tail[0], optional

    # ---- measured ----
    pos_ist: float = 0.0  # uplink field 4
    vel_ist: float = 0.0  # uplink field 5

    # ---- helpers (decoded) ----
    estop_active: bool = False
    fault_active: bool = False
    enabled: bool = False


@dataclass(frozen=True)
class AxisRequest:
    """Operator/controller intent for this tick."""

    want_enable: bool = False
    want_motion: bool = False
    want_claim: bool = True  # usually true in your controller
    want_resync: bool = False
    want_reset_estop: bool = False

    # setpoints (already ramped/clamped elsewhere)
    cmd_speed: float = 0.0
    cmd_pos: float = 0.0

    # if you want to push params (Modus == 'w') later:
    write_params: bool = False


@dataclass(frozen=True)
class AxisCommand:
    """Semantic command; adapter turns this into legacy downlink tokens."""

    # downlink base:
    modus: str  # 'E' / 'w' / 'xx'
    own_pid_tx: str  # controller pid string
    control_pid_tx: int  # legacy field (keep 0 unless needed)
    intent_str: str  # "True"/"False"
    control_in: int  # legacy control word
    guide_control_ui: int
    speed_soll: float
    guide_speed_soll: float
    pos_soll: float
    estop_reset: int  # dword
    resync: float  # 0.0/1.0
    gui_nothalt_in: int  # 0/1

    # optional write-extension:
    write_params: bool = False
    params: Optional[dict] = None
