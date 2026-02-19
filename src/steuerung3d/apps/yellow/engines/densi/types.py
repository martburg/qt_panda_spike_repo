"""Shared DenSi type definitions.

These enums were originally defined inside the DenSi Qt controller. They are
moved here so the Qt-free DenSiEngine can own the semantics.

Semantics: keep names and members identical to the legacy controller.
"""

from __future__ import annotations

from enum import Enum, auto


class EStopState(Enum):
    """Device-local Safety/EStop ladder state."""

    ESTOP = auto()
    IDLE = auto()
    ARMED = auto()
    READY = auto()


class L0Top(Enum):
    """DenSi (device-local) top-level connection state.

    We model whether the device has seen at least one command frame.
    Connection arbitration/ownership is handled elsewhere in the legacy stack;
    for now we accept any incoming connection.
    """

    START = auto()       # no command frames seen yet
    CONNECTED = auto()   # at least one command frame seen recently


class L0Sub(Enum):
    """DenSi (device-local) connected substates."""

    IDLE = auto()
    RESETTING_ESTOP = auto()
    EDIT_PARAMETER = auto()
