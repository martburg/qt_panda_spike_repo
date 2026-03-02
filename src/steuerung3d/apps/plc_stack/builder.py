from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol

from steuerung3d.adapters.links.udp_link import UdpLink
from steuerung3d.adapters.plc.multi_plc_device import MultiPlcDevice
from steuerung3d.adapters.plc.plc_codec import PlcCodec
from steuerung3d.adapters.plc.plc_config import PlcWireSpec
from steuerung3d.adapters.plc.plc_endpoint import PlcEndpoint
from steuerung3d.adapters.plc.validate import validate_endpoints
from steuerung3d.common.timebase import Timebase
from steuerung3d.config.plc_stack_config import PlcStackConfig
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.recording import JsonlRecorder, LoggedTransport
from steuerung3d.protocol.transport import InMemTransport

# --------------------
# Types
# --------------------

DeviceStep = Callable[[MachineState, object, float], None]
# Note: device_step signature in the current engine is (state, command_frame, dt).
# We intentionally type 'command_frame' as 'object' here to keep the app boundary light.


class LinkFactory(Protocol):
    def __call__(self, *, bind: tuple[str, int], target: tuple[str, int]): ...  # pragma: no cover


class CodecFactory(Protocol):
    def __call__(self, *, spec: PlcWireSpec): ...  # pragma: no cover


# --------------------
# Runtime bundle
# --------------------


@dataclass
class PlcStackRuntime:
    cfg: PlcStackConfig
    transport: InMemTransport  # may be wrapped (LoggedTransport)
    timebase: Timebase
    state: MachineState
    engine: CoreEngine


# --------------------
# Helpers
# --------------------


def collect_axes(cfg: PlcStackConfig) -> list[str]:
    axes: list[str] = []
    for ep in cfg.plc_endpoints:
        axes.extend(ep.axis_ids)
    # de-dup while preserving order
    seen = set()
    out: list[str] = []
    for a in axes:
        if a not in seen:
            out.append(a)
            seen.add(a)
    return out


def build_transport(cfg: PlcStackConfig) -> tuple[InMemTransport, JsonlRecorder]:
    raw = InMemTransport()
    rec = JsonlRecorder(Path(cfg.app.log_path))
    transport = LoggedTransport(raw, rec)  # type: ignore[assignment]
    return transport, rec


# --------------------
# PLC device construction (importable + testable)
# --------------------


def build_plc_device(
    cfg: PlcStackConfig,
    *,
    link_factory: LinkFactory | None = None,
    codec_factory: CodecFactory | None = None,
) -> tuple[MultiPlcDevice, list[PlcEndpoint]]:
    """Build the PLC edge adapter (UDP link + codec) from config.

    Why factories?
      - The real UdpLink may bind sockets in __init__ (implementation-dependent).
      - Unit tests should not open sockets.
      - Passing link_factory / codec_factory lets tests use cheap fakes.

    Returns:
      (device, endpoints)
    """
    if link_factory is None:

        def link_factory(*, bind, target):
            return UdpLink(bind=bind, target=target)

    if codec_factory is None:

        def codec_factory(*, spec):
            return PlcCodec(spec=spec)

    endpoints: list[PlcEndpoint] = []
    for ep_cfg in cfg.plc_endpoints:
        spec = PlcWireSpec(
            axis_ids=list(ep_cfg.axis_ids),
            delimiter=ep_cfg.delimiter,
            encoding=ep_cfg.encoding,
            float_fmt=ep_cfg.float_fmt,
            true_token=ep_cfg.true_token,
            false_token=ep_cfg.false_token,
        )
        codec = codec_factory(spec=spec)
        link = link_factory(
            bind=(ep_cfg.bind_host, ep_cfg.bind_port),
            target=(ep_cfg.target_host, ep_cfg.target_port),
        )

        endpoints.append(
            PlcEndpoint(
                name=ep_cfg.name,
                axis_ids=list(ep_cfg.axis_ids),
                link=link,
                codec=codec,
            )
        )

    validate_endpoints(endpoints)
    return MultiPlcDevice(endpoints=endpoints), endpoints


# --------------------
# Core construction (real app wiring)
# --------------------


def build_core(
    cfg: PlcStackConfig, *, device_step: DeviceStep, enable_logging: bool = True
) -> PlcStackRuntime:
    """Build the core runtime using the real plc_stack wiring.

    - axes come from cfg.plc_endpoints[*].axis_ids
    - transport is InMemTransport (optionally wrapped with JSONL logging)
    - engine is CoreEngine with apply_intent and provided device_step
    """
    transport: InMemTransport
    rec: Optional[JsonlRecorder] = None

    if enable_logging:
        transport, rec = build_transport(cfg)
    else:
        transport = InMemTransport()

    tb = Timebase(dt_s=float(cfg.app.dt_s))
    st = MachineState()
    for a in collect_axes(cfg):
        st.ensure_axis(a)

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=transport.drain_intents,
        handle_intent=apply_intent,
        device_step=device_step,
        on_snapshot=transport.publish_telemetry,
        on_command_frame=(rec.record_command_frame if rec is not None else None),
    )

    return PlcStackRuntime(cfg=cfg, transport=transport, timebase=tb, state=st, engine=eng)
