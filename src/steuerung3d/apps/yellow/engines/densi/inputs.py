"""Densi runtime input types (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from steuerung3d.core.command_frame import CommandFrame


def _new_estop_toggle_list() -> list[DensiEstopToggle]:
    return []


@dataclass(frozen=True)
class DensiEstopToggle:
    key: str
    checked: bool


@dataclass
class DensiUiInputs:
    es_start_clicked: bool = False
    estop_reset_clicked: bool = False
    estop_all_set_clicked: bool = False
    estop_all_clear_clicked: bool = False
    diag_resync_clicked: bool = False
    estop_bit_toggles: list[DensiEstopToggle] = field(default_factory=_new_estop_toggle_list)


@dataclass(frozen=True)
class DensiInputs:
    frames: List[CommandFrame]
    now_ns: int
    ui: DensiUiInputs = field(default_factory=DensiUiInputs)
