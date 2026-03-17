from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import JoyState


class AxisPhase(str, Enum):
    """Supervisor-visible state of one supervised axis/unit."""

    ESTOP = "ESTOP"
    IDLE = "IDLE"
    ARMED = "ARMED"
    READY = "READY"
    LIVE = "LIVE"
    STALE = "STALE"


PairPhase = AxisPhase


@dataclass(frozen=True, init=False)
class AxisConfig:
    """Configuration for one supervised axis/unit.

    Axis/unit naming is canonical inside the supervisor. The older pair-centric
    constructor shape remains supported as a compatibility boundary.
    """

    axis_id: str
    unit_id: str
    densi_id: str
    hip_id: str
    selected: bool
    densi_action_out: str
    hip_launch: str
    densi_launch: str

    def __init__(
        self,
        *,
        axis_id: str,
        unit_id: str = "",
        pair_id: str = "",
        densi_id: str = "",
        hip_id: str = "",
        selected: bool = True,
        densi_action_out: str = "",
        hip_launch: str = "",
        densi_launch: str = "",
    ) -> None:
        resolved_unit_id = str(unit_id or pair_id or axis_id)
        object.__setattr__(self, "axis_id", str(axis_id))
        object.__setattr__(self, "unit_id", resolved_unit_id)
        object.__setattr__(self, "densi_id", str(densi_id or axis_id))
        object.__setattr__(self, "hip_id", str(hip_id))
        object.__setattr__(self, "selected", bool(selected))
        object.__setattr__(self, "densi_action_out", str(densi_action_out))
        object.__setattr__(self, "hip_launch", str(hip_launch))
        object.__setattr__(self, "densi_launch", str(densi_launch))

    @property
    def pair_id(self) -> str:
        """Backward-compatible alias for older pair-centric call sites."""

        return self.unit_id


PairConfig = AxisConfig


@dataclass(frozen=True, init=False)
class SupervisorProfile:
    supervisor_id: str
    title: str
    cycle_ms: int
    telem_in: str
    intent_out: str
    gui: bool
    stale_after_ms: int
    launch_stack: str
    axes: tuple[AxisConfig, ...]

    def __init__(
        self,
        *,
        supervisor_id: str,
        title: str,
        cycle_ms: int,
        telem_in: str,
        intent_out: str,
        gui: bool = True,
        stale_after_ms: int = 800,
        launch_stack: str = "",
        axes: tuple[AxisConfig, ...] = (),
        pairs: tuple[AxisConfig, ...] = (),
    ) -> None:
        resolved_axes = tuple(axes or pairs)
        object.__setattr__(self, "supervisor_id", str(supervisor_id))
        object.__setattr__(self, "title", str(title))
        object.__setattr__(self, "cycle_ms", int(cycle_ms))
        object.__setattr__(self, "telem_in", str(telem_in))
        object.__setattr__(self, "intent_out", str(intent_out))
        object.__setattr__(self, "gui", bool(gui))
        object.__setattr__(self, "stale_after_ms", int(stale_after_ms))
        object.__setattr__(self, "launch_stack", str(launch_stack))
        object.__setattr__(self, "axes", resolved_axes)

    @property
    def pairs(self) -> tuple[AxisConfig, ...]:
        return self.axes


@dataclass(frozen=True, init=False)
class AxisRow:
    axis_id: str
    unit_id: str
    densi_id: str
    hip_id: str
    selected: bool
    phase: AxisPhase
    estop: bool
    livetick: int
    pos: float
    vel: float
    estop_word: int = 0
    estop_dots: tuple[bool | None, ...] = ()
    livetick_diff: int = 0
    stale: bool = False
    hip_open_count: int = 0

    def __init__(
        self,
        *,
        axis_id: str,
        densi_id: str,
        hip_id: str,
        selected: bool,
        phase: AxisPhase,
        estop: bool,
        livetick: int,
        pos: float,
        vel: float,
        unit_id: str = "",
        pair_id: str = "",
        estop_word: int = 0,
        estop_dots: tuple[bool | None, ...] = (),
        livetick_diff: int = 0,
        stale: bool = False,
        hip_open_count: int = 0,
    ) -> None:
        object.__setattr__(self, "axis_id", str(axis_id))
        object.__setattr__(self, "unit_id", str(unit_id or pair_id or axis_id))
        object.__setattr__(self, "densi_id", str(densi_id))
        object.__setattr__(self, "hip_id", str(hip_id))
        object.__setattr__(self, "selected", bool(selected))
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "estop", bool(estop))
        object.__setattr__(self, "estop_word", int(estop_word))
        object.__setattr__(
            self, "estop_dots", tuple((None if v is None else bool(v)) for v in estop_dots)
        )
        object.__setattr__(self, "livetick", int(livetick))
        object.__setattr__(self, "livetick_diff", int(livetick_diff))
        object.__setattr__(self, "pos", float(pos))
        object.__setattr__(self, "vel", float(vel))
        object.__setattr__(self, "stale", bool(stale))
        object.__setattr__(self, "hip_open_count", int(hip_open_count))

    @property
    def pair_id(self) -> str:
        """Backward-compatible alias for older pair-centric row consumers."""

        return self.unit_id


PairRow = AxisRow


@dataclass(frozen=True)
class SupervisorSnapshot:
    title: str
    status_text: str
    rows: tuple[AxisRow, ...]
    joy: JoyState = field(default_factory=JoyState)
    hip_open_total: int = 0


@dataclass(frozen=True)
class DensiRemoteAction:
    action: str
    value: bool | None = None


@dataclass(frozen=True)
class OutboundBatch:
    intents: tuple[Intent, ...] = ()
    densi_actions: dict[str, tuple[DensiRemoteAction, ...]] = field(default_factory=dict)
    joy_update_changed: bool = False
