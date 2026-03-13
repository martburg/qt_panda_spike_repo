from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


@dataclass(frozen=True)
class PairRef:
    pair_id: str
    axis_id: str
    densi_id: str
    hip_id: str


@dataclass(frozen=True)
class SupervisorMember:
    member_id: str
    member_kind: Literal["pair"]
    target_id: str
    order_key: int = 0


@dataclass(frozen=True)
class SupervisorSpec:
    supervisor_id: str
    name: str
    members: tuple[SupervisorMember, ...]
    kinematics_id: str | None = None


class PairPhase(str, Enum):
    OFFLINE = "offline"
    UNATTACHED = "unattached"
    ATTACHED = "attached"
    IDLE = "idle"
    ARMED = "armed"
    BRAKE_GRACE = "brake_grace"
    READY = "ready"
    LIVE = "live"
    FAULT = "fault"


class PairInteractionMode(str, Enum):
    VIEWING = "viewing"
    EDITING_PARAMETERS = "editing_parameters"


class PairAction(str, Enum):
    RESET_ESTOP = "reset_estop"
    ESTART = "estart"
    CHECK_ES_TASTER = "check_es_taster"
    EDIT_PARAMETERS = "edit_parameters"
    WRITE_PARAMETERS = "write_parameters"
    CANCEL_EDIT = "cancel_edit"


class ControlSource(str, Enum):
    GUI = "gui"
    FREDERIK = "frederik"
    SYSTEM = "system"


@dataclass(frozen=True)
class PairControlInputs:
    estop_reset_input: bool = False
    estart_input: bool = False
    chk_es_taster_input: bool = False


@dataclass(frozen=True)
class PairFacts:
    attached: bool
    stale: bool
    fault: bool
    estop_reset_input: bool
    estart_input: bool
    chk_es_taster_input: bool
    brake_grace_active: bool
    ready_actual: bool
    deadman_active: bool
    live_motion_active: bool
    param_edit_active: bool
    position: float | None
    velocity: float | None
    banner_estate: str = ""


@dataclass(frozen=True)
class PairActionSurface:
    primary_action: PairAction | None
    allowed_actions: frozenset[PairAction]
    blocking_reason: str


@dataclass(frozen=True)
class PairStatus:
    ref: PairRef
    facts: PairFacts
    phase: PairPhase
    interaction_mode: PairInteractionMode
    actions: PairActionSurface


@dataclass(frozen=True)
class SupervisorPose:
    position: dict[str, float]
    velocity: dict[str, float]
    dofs: dict[str, float]
    valid: bool
    summary: str


@dataclass(frozen=True)
class PairResetEstopRequest:
    pair_id: str
    source: ControlSource


@dataclass(frozen=True)
class PairResetEstopEligibility:
    pair_id: str
    eligible: bool
    reason: str


@dataclass(frozen=True)
class PairResetEstopIssueResult:
    pair_id: str
    issued: bool
    eligible: bool
    reason: str
    source: ControlSource


@dataclass(frozen=True)
class BatchResetEstopResult:
    requested_pair_ids: tuple[str, ...]
    results: tuple[PairResetEstopIssueResult, ...]

    @property
    def issued_pair_ids(self) -> tuple[str, ...]:
        return tuple(result.pair_id for result in self.results if result.issued)

    @property
    def blocked_pair_ids(self) -> tuple[str, ...]:
        return tuple(result.pair_id for result in self.results if not result.issued)
