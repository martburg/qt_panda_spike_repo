from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


class RigMode(str, Enum):
    """Rig-level workflow mode.

    Separate from :class:`steuerung3d.core.mode.Mode`.

    - Mode is the global safety/motion gate (ESTOP/FAULT/IDLE/LIVE)
    - RigMode is the operator workflow (discovery/setup/sync/recover)

    The config-freeze boundary is from ARMED_SYNC onwards.
    """

    DISCOVERY = "DISCOVERY"
    SETUP_MANUAL = "SETUP_MANUAL"
    ARMED_SYNC = "ARMED_SYNC"        # frozen config; no motion
    SYNC_ACTIVE = "SYNC_ACTIVE"      # frozen config; kinematics active
    SYNC_RECOVER = "SYNC_RECOVER"    # frozen config; recover/resync only
    FAULT_SYNC = "FAULT_SYNC"        # frozen config; motion inhibited


@dataclass
class DensiRuntime:
    """Runtime registry record for a single DenSi (PLC/winch)."""

    device_id: str

    # when we last saw telemetry (core tick + device tick)
    last_seen_core_tick: int = -1
    last_seen_device_tick: int = -1

    # claim/pairing
    claimed_by_hip: str = ""  # hip_id

    # rig membership / config
    participating: bool = False
    anchor_xyz: Optional[Tuple[float, float, float]] = None


@dataclass
class RigSyncConfig:
    """Frozen configuration snapshot created when entering ARMED_SYNC."""

    participating: Tuple[str, ...] = ()
    anchors: Dict[str, Tuple[float, float, float]] = field(default_factory=dict)


@dataclass
class RecoverPlan:
    """Active recovery plan in SYNC_RECOVER."""

    active: bool = False
    target_lengths: Dict[str, float] = field(default_factory=dict)

    # simple proportional 'go to target length' controller on measured pos
    kp: float = 1.0
    v_max: float = 0.25
    tol: float = 1e-3

    # safety
    started_tick: int = 0
    timeout_ticks: int = 0  # 0 means disabled
