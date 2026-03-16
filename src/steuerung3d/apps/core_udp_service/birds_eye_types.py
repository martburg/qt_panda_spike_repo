from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, TypedDict


class CommandAxisLike(Protocol):
    vel: float


class CommandFrameLike(Protocol):
    axes: Mapping[str, CommandAxisLike]
    estop_reset: bool
    resync: bool


class BirdsEyeStatusLike(Protocol):
    def emit_every(self, *, level: str, summary: str, fields: dict[str, object]) -> None: ...


class BirdsEyeJoyLike(Protocol):
    selected_axes: Sequence[str]


class BirdsEyeStateLike(Protocol):
    joy: BirdsEyeJoyLike | None
    axis_claims: Mapping[str, str]
    estop_reset_denied_count_by_axis: Mapping[str, int]
    core_motion_allowed: bool
    core_axis_gate: Mapping[str, Mapping[str, object]]


class BirdsEyeSnapLike(Protocol):
    estop: bool
    fault: bool
    core_mode: str
    tick: int
    densis: Mapping[str, object]


class LastSeenLike(TypedDict, total=False):
    intent_ts: float
    dev_telem_ts: float
    cmd_ts: float
    ui_telem_ts: float
    c2_telem_ts: float


class LastIntentsMetaLike(TypedDict, total=False):
    count: int
    types: list[str]


@dataclass(frozen=True)
class BirdsEyeAgeFacts:
    age_int: float | None
    age_dev: float | None
    age_cmd: float | None
    age_ui: float | None
    age_c2: float | None
    stale: bool


@dataclass(frozen=True)
class BirdsEyeMotionFacts:
    axes_snapshot: list[dict[str, object]]
    blocked_by: list[str]
    blocked_payload: list[dict[str, object]]
    cmd_frame: CommandFrameLike | None
    selected_lanes: list[str]
    attached_lanes: list[str]
    resolved_moving_targets: list[str]
    local_manual_axes: list[str]
    joy_dm: bool
    joy_sel: bool
    intents_types_str: str
    reset_denied_by_axis: dict[str, int]
    reset_denied_total: int
    devices: list[str]
