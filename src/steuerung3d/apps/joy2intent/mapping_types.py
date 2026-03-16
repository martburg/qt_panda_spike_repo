from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


class _JoyBindingsLike(Protocol):
    @property
    def axes(self) -> Mapping[str, int]: ...

    @property
    def buttons(self) -> Mapping[str, int | Sequence[int]]: ...

    @property
    def deadzone(self) -> float: ...

    @property
    def expo(self) -> float: ...

    @property
    def select_buttons(self) -> Sequence[int | Sequence[int]]: ...

    @property
    def invert(self) -> Mapping[str, bool]: ...


class _JoyLimitsLike(Protocol):
    @property
    def fine_scale(self) -> float: ...

    def max_speed(self) -> float: ...


class _IndexedJoyStateLike(Protocol):
    prev_deadman: bool
    deadman_prev: bool
    prev_active_winch_idxs: set[int]
    enabled_winch_ids: set[str]


class _NamedJoyStateLike(Protocol):
    prev_deadman: bool
    deadman_prev: bool
    prev_active_winch_idxs: set[int]
    enabled_winch_ids: set[str]


_JoyStateLike = _IndexedJoyStateLike | _NamedJoyStateLike


class _JoyReportLike(Protocol):
    @property
    def axes(self) -> Sequence[float]: ...

    @property
    def buttons(self) -> Sequence[int]: ...


@dataclass(frozen=True)
class JoyInputFacts:
    pressed: set[int]
    axes: list[float]
    deadman: bool
    fine: bool
    soll_speed: float
    selected_set: set[str]
    rig_ids: list[str]
    use_contextual_local_manual: bool
    motion_enabled: bool


@dataclass(frozen=True)
class PreviousActivity:
    prev_deadman: bool
    active_ids: set[str]


@dataclass(frozen=True)
class RateFacts:
    rate: float


@dataclass(frozen=True)
class ActiveSelection:
    selected_ids: set[str]
