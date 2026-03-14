from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import JoyState


class PairPhase(str, Enum):
    ESTOP = "ESTOP"
    IDLE = "IDLE"
    ARMED = "ARMED"
    READY = "READY"
    LIVE = "LIVE"
    STALE = "STALE"


@dataclass(frozen=True)
class PairConfig:
    pair_id: str
    axis_id: str
    densi_id: str
    hip_id: str
    selected: bool = True
    densi_action_out: str = ""
    hip_launch: str = ""
    densi_launch: str = ""


@dataclass(frozen=True)
class SupervisorProfile:
    supervisor_id: str
    title: str
    cycle_ms: int
    telem_in: str
    intent_out: str
    gui: bool = True
    stale_after_ms: int = 800
    launch_stack: str = ""
    pairs: tuple[PairConfig, ...] = ()


@dataclass(frozen=True)
class PairRow:
    pair_id: str
    axis_id: str
    densi_id: str
    hip_id: str
    selected: bool
    phase: PairPhase
    estop: bool
    livetick: int
    pos: float
    vel: float
    stale: bool = False


@dataclass(frozen=True)
class SupervisorSnapshot:
    title: str
    status_text: str
    rows: tuple[PairRow, ...]
    joy: JoyState = field(default_factory=JoyState)


@dataclass(frozen=True)
class DensiRemoteAction:
    action: str
    value: bool | None = None


@dataclass(frozen=True)
class OutboundBatch:
    intents: tuple[Intent, ...] = ()
    densi_actions: dict[str, tuple[DensiRemoteAction, ...]] = field(default_factory=dict)
    joy_update_changed: bool = False
