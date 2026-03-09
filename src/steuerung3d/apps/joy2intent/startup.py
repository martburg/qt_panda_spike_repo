from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from steuerung3d.core.net import parse_hostport
from steuerung3d.core.status import StatusEmitter
from steuerung3d.protocol.udp_channels import UdpControlContextIn, UdpIntentOut, UdpRawControlsIn
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat

from .config import Joy2IntentConfig, load_joy2intent_config
from .mapping import JoyBindings, JoyLimits, JoyRig
from .state import JoyState


@dataclass(frozen=True)
class Joy2IntentRuntime:
    cfg: Joy2IntentConfig
    raw_in: UdpRawControlsIn
    context_in: UdpControlContextIn
    intent_out: UdpIntentOut
    state: JoyState
    rig: JoyRig
    bindings: JoyBindings
    limits: JoyLimits
    hb: Heartbeat
    ch: ChangeTracker
    dt: float
    status: StatusEmitter | None


def load_runtime(
    *, config_path: str, raw_in: str | None, intent_out: str | None
) -> Joy2IntentRuntime:
    cfg = load_joy2intent_config(Path(config_path))
    if raw_in:
        cfg = replace(cfg, raw_in=parse_hostport(str(raw_in)))
    if intent_out:
        cfg = replace(cfg, intent_out=parse_hostport(str(intent_out)))

    return Joy2IntentRuntime(
        cfg=cfg,
        raw_in=UdpRawControlsIn.bind(cfg.raw_in),
        context_in=UdpControlContextIn.bind(cfg.context_in),
        intent_out=UdpIntentOut.connect(cfg.intent_out),
        state=JoyState(mode=cfg.default_mode),
        rig=JoyRig(winches=cfg.winches),
        bindings=JoyBindings(
            axes=cfg.axes,
            buttons=cfg.buttons,
            select_buttons=list(cfg.select_buttons or []),
            invert=cfg.invert,
            deadzone=cfg.deadzone,
            expo=cfg.expo,
        ),
        limits=JoyLimits(max_winch_mps=cfg.max_winch_mps, fine_scale=cfg.fine_scale),
        hb=Heartbeat("joy2intent", interval_s=1.0),
        ch=ChangeTracker(),
        dt=1.0 / max(1.0, cfg.tick_hz),
        status=StatusEmitter.from_env(default_service="joy2intent"),
    )
