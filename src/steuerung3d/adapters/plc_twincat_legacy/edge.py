from __future__ import annotations

"""Transport-facing edge adapter for the frozen TwinCAT legacy UDP protocol.

The Beckhoff/TwinCAT PLC code is frozen and uses two strict UDP flows:

1) Controller -> PLC: semicolon-delimited, order-sensitive *downlink* frame.
2) PLC -> Controller: semicolon-delimited *uplink* status frame.

This adapter bridges that wire protocol to the internal TransportV2 seam:
it consumes CommandFrame(s) and publishes TelemetrySnapshot(s).
"""

import os
import socket
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot
from steuerung3d.protocol.transport import TransportV2

from .codec import TwinCATLegacyWinchCodec, TwinCATLegacyWinchDownlink, parse_float, parse_int


@dataclass
class TwinCATLegacyWinchEdge:
    """One-axis edge adapter.

    It expects the core to emit CommandFrame continuously (watchdog behavior).
    If frames are missed, we continue sending the last known command, but still
    attempt to advance the watchdog tick using wall time.
    """

    axis_id: str
    transport: TransportV2

    plc_remote: Tuple[str, int]  # (plc_ip, plc_port) typically (..., 15001)
    local_bind: Tuple[str, int]  # (controller_ip, local_port) typically (..., 1500x)

    timeout_s: float = 0.02
    dt_s: float = 0.01

    codec: TwinCATLegacyWinchCodec = field(default_factory=TwinCATLegacyWinchCodec)

    # session/ownership
    own_pid: str = field(default_factory=lambda: str(os.getpid()))
    control_pid_tx: int = 0
    intent: bool = True
    modus: str = "E"
    guide_control_ui: int = 0
    guide_soll_speed: float = 0.0
    estop_reset_word: int = 0
    resync: float = 0.0
    gui_not_halt: int = 0

    _sock: Optional[socket.socket] = None
    _last_cmd: Optional[CommandFrame] = None
    _last_cmd_rx_ns: int = 0

    # PosSoll integrator + edge detect
    _pos_soll: float = 0.0
    _last_enable: bool = False

    # last seen device tick (LifetickUItx)
    _device_tick: int = 0

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _ensure_sock(self) -> socket.socket:
        if self._sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(self.timeout_s)
            s.bind(self.local_bind)
            self._sock = s
        return self._sock

    def _select_cmd(self) -> Optional[CommandFrame]:
        frames = self.transport.drain_command_frames(limit=50)
        if frames:
            self._last_cmd = frames[-1]
            self._last_cmd_rx_ns = time.monotonic_ns()
        return self._last_cmd

    def step_once(self) -> None:
        """Perform one edge tick: consume latest command, talk to PLC, publish telemetry."""
        cmd = self._select_cmd()
        if cmd is None:
            return

        sock = self._ensure_sock()

        sp = (cmd.axes or {}).get(self.axis_id)
        enable_cmd = bool(sp.enable) if sp is not None else False
        vel_cmd = float(sp.vel) if sp is not None else 0.0

        # Use echo tick if present (lets UI measure round trip), else CommandFrame.tick.
        if isinstance(getattr(cmd, "lifetick_echo", None), dict):
            lifetick = int(cmd.lifetick_echo.get(self.axis_id, cmd.tick)) & 0xFFFF
        else:
            lifetick = int(cmd.tick) & 0xFFFF

        # Apply global safety gating.
        enable = enable_cmd and (not cmd.estop) and (not cmd.fault)
        vel = vel_cmd if enable else 0.0

        # Following-error friendly: on rising enable edge, rebase PosSoll to last PosIst.
        rebased = enable and (not self._last_enable)
        if rebased:
            # Use last published position as our best estimate.
            # If PLC is already enabled and we missed telemetry, PLC will ignore anyway.
            # (And on clean start this equals the most recent PosIst.)
            self._pos_soll = float(self._pos_soll)
        elif enable:
            self._pos_soll += vel * float(self.dt_s)
        self._last_enable = enable

        # Downlink legacy knobs can be driven by higher layers via CommandFrame
        # (defaults keep stable behavior when absent).
        control_in = 1 if enable else 0
        estop_reset_word = int(self.estop_reset_word)
        if bool(getattr(cmd, "estop_reset", False)):
            # Momentary request from core. The PLC expects a DWORD; keep it simple here.
            estop_reset_word = 1

        intent = bool(getattr(cmd, "intent", self.intent))
        resync = float(1.0 if bool(getattr(cmd, "resync", False)) else float(self.resync))
        gui_not_halt = int(1 if bool(getattr(cmd, "gui_not_halt", False)) else int(self.gui_not_halt))

        down = TwinCATLegacyWinchDownlink(
            lifetick=lifetick,
            modus=self.modus,
            own_pid=self.own_pid,
            control_pid_tx=int(self.control_pid_tx),
            intent=bool(intent),
            control_in=int(control_in),
            guide_control_ui=int(self.guide_control_ui),
            speed_soll=float(vel),
            guide_soll_speed=float(self.guide_soll_speed),
            pos_soll=float(self._pos_soll),
            estop_reset=int(estop_reset_word),
            resync=float(resync),
            gui_not_halt=int(gui_not_halt),
            write_params=None,
        )

        sock.sendto(self.codec.encode_downlink(down).encode("utf-8"), self.plc_remote)

        # Receive telemetry best-effort.
        try:
            data, _addr = sock.recvfrom(65535)
        except socket.timeout:
            return
        except ConnectionResetError:
            # Windows: ICMP Port Unreachable -> WSAECONNRESET on recvfrom
            return
        except OSError as e:
            if getattr(e, "winerror", None) == 10054:
                return
            raise

        txt = data.decode("utf-8", errors="replace").strip()
        if not txt:
            return

        up = self.codec.decode_uplink(txt)
        f = up.fields

        device_tick = parse_int(f.get("LifetickUItx", "0"), default=int(self._device_tick))
        self._device_tick = int(device_tick) & 0xFFFF

        pos_ist = float(parse_float(f.get("PosIst", "0"), default=float(self._pos_soll)))
        vel_ist = float(parse_float(f.get("SpeedIstUI", "0"), default=0.0))

        status_word = parse_int(f.get("Status", "0"), default=0)
        guide_status_word = parse_int(f.get("GuideStatus", "0"), default=0)
        estop_status = parse_int(f.get("EStopStatus", "0"), default=0)
        STATUS_READY = 4356
        enabled = (estop_status == 0) and (status_word == STATUS_READY)
        fault = (estop_status != 0) or (status_word != 0)

        # Keep our integrator close to measured position (helps after packet loss).
        self._pos_soll = float(pos_ist)

        snap = TelemetrySnapshot(
            tick=int(cmd.tick),
            t_s=float(cmd.t_s),
            mode=str(cmd.mode),
            core_mode=str(cmd.mode),
            estop=bool(cmd.estop),
            fault=bool(cmd.fault) or bool(fault),
            axes={
                self.axis_id: AxisTelemetry(
                    pos=float(pos_ist),
                    vel=float(vel_ist),
                    enabled=bool(enabled),
                    fault=bool(fault),
                    device_tick=int(self._device_tick) & 0xFFFF,
                    lifetick_rx=int(lifetick) & 0xFFFF,
                    lifetick_age=(int(self._device_tick) - int(lifetick)) & 0xFFFF,
                    status_word=int(status_word),
                    guide_status_word=int(guide_status_word),
                )
            },
        )

        self.transport.publish_telemetry(snap)
