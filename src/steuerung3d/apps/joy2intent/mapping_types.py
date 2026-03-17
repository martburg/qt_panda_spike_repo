from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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


@runtime_checkable
class _IndexedJoyStateLike(Protocol):
    @property
    def prev_deadman(self) -> bool: ...

    @prev_deadman.setter
    def prev_deadman(self, value: bool) -> None: ...

    @property
    def prev_active_winch_idxs(self) -> set[int]: ...

    @prev_active_winch_idxs.setter
    def prev_active_winch_idxs(self, value: set[int]) -> None: ...


@runtime_checkable
class _NamedJoyStateLike(Protocol):
    @property
    def deadman_prev(self) -> bool: ...

    @deadman_prev.setter
    def deadman_prev(self, value: bool) -> None: ...

    @property
    def enabled_winch_ids(self) -> set[str]: ...

    @enabled_winch_ids.setter
    def enabled_winch_ids(self, value: set[str]) -> None: ...


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
