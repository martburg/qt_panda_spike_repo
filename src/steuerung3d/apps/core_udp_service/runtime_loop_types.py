from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.axis_router import AxisRouter
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.udp_channels import (
    UdpControlContextOut,
    UdpIntentIn,
    UdpTelemetryFanout,
    UdpTelemetryOut,
)
from steuerung3d.protocol.udp_plc_channels import UdpPlcCommandOut, UdpPlcTelemetryIn

from .runtime_handlers import DeviceStepper, SnapshotHandler


class CoreUdpServiceArgs(Protocol):
    intent_in: str
    control_context_target: str
    ui_telem_disable: bool
    ui_telem_target: list[str]
    ui_telem_host: str
    ui_telem_base: str | None
    ui_telem_count: int
    ui_telem_mode: str
    c2_telem_target: list[str]
    c2_telem_host: str
    c2_telem_base: str | None
    c2_telem_count: int
    dev_telem_in: str
    dev_cmd_target: list[str]
    dev_cmd_host: str
    dev_cmd_base: str | None
    dev_cmd_count: int
    axis: list[str]
    dt: float


@dataclass(frozen=True)
class UdpEndpoints:
    intent_in_bind: tuple[str, int]
    op_intent_in: UdpIntentIn
    control_context_out: UdpControlContextOut
    ui_telem_targets: list[tuple[str, int]]
    op_telem_outs: list[UdpTelemetryOut]
    c2_telem_targets: list[tuple[str, int]]
    c2_telem_outs: list[UdpTelemetryOut]
    c2_fanout: UdpTelemetryFanout | None
    dev_telem_bind: tuple[str, int]
    dev_telem_in: UdpPlcTelemetryIn
    dev_cmd_targets: list[tuple[str, int]]
    dev_cmd_outs: list[UdpPlcCommandOut]


@dataclass(frozen=True)
class CoreRuntimeSetup:
    tb: Timebase
    state: MachineState
    axis_ids: list[str]
    router: AxisRouter
    drain_intents: object
    device_step: DeviceStepper
    on_snapshot: SnapshotHandler
    runner: CoreRunner


@dataclass(frozen=True)
class RuntimeStats:
    stats: dict[str, int]
    last_intents_meta: dict[str, object]
    last_seen: dict[str, object]
    t0: float
