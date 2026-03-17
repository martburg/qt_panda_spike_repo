from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, TypedDict


class CommandAxisLike(Protocol):
    @property
    def vel(self) -> float: ...

    @property
    def enable(self) -> bool: ...


class CommandFrameLike(Protocol):
    @property
    def axes(self) -> Mapping[str, CommandAxisLike]: ...

    @property
    def estop_reset(self) -> bool: ...

    @property
    def resync(self) -> bool: ...


class BirdsEyeStatusLike(Protocol):
    def emit_every(self, *, level: str, summary: str, fields: dict[str, object]) -> None: ...


class BirdsEyeJoyLike(Protocol):
    @property
    def selected_axes(self) -> Sequence[str]: ...


class BirdsEyeStateLike(Protocol):
    @property
    def joy(self) -> BirdsEyeJoyLike | None: ...

    @property
    def axis_claims(self) -> Mapping[str, str]: ...

    @property
    def estop_reset_denied_count_by_axis(self) -> Mapping[str, int]: ...

    @property
    def core_motion_allowed(self) -> bool: ...

    @property
    def core_axis_gate(self) -> Mapping[str, Mapping[str, object]]: ...


class BirdsEyeAxisDetailStateLike(BirdsEyeStateLike, Protocol):
    @property
    def core_blocked_by(self) -> Sequence[object]: ...

    @property
    def axis_cmd(self) -> Mapping[str, object]: ...

    @property
    def lease_axis_holders(self) -> Mapping[str, Sequence[str]]: ...

    @property
    def fault(self) -> bool: ...

    def claim_owner(self, axis_id: str) -> str | None: ...


class BirdsEyeSnapLike(Protocol):
    @property
    def estop(self) -> bool: ...

    @property
    def fault(self) -> bool: ...

    @property
    def core_mode(self) -> str: ...

    @property
    def tick(self) -> int: ...

    @property
    def densis(self) -> Mapping[str, object]: ...

    @property
    def estop_status_word(self) -> int: ...


class BirdsEyeRouterLike(Protocol):
    @property
    def last_dev_estop_word_by_axis(self) -> Mapping[str, int]: ...


class LastSeenLike(TypedDict, total=False):
    intent_ts: float | None
    dev_telem_ts: float | None
    cmd_ts: float | None
    ui_telem_ts: float | None
    c2_telem_ts: float | None


class LastIntentsMetaLike(TypedDict, total=False):
    count: int
    types: Sequence[str]


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
