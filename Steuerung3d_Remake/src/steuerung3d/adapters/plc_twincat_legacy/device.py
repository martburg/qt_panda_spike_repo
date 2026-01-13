# src/steuerung3d/adapters/plc_legacy_winch/device.py
from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from typing import Optional, Tuple

from steuerung3d.adapters.plc_twincat_legacy.codec import (
    TwinCATLegacyWinchCodec,
    TwinCATLegacyWinchDownlink,
    parse_float,
    parse_int,
)

from steuerung3d.core.axis_types import AxisTelemetry as LegacyAxisTelemetry


@dataclass
class TwinCATLegacyWinchUdpDevice:
    """
    Legacy TwinCAT winch UDP boundary (Anton/Burt/Cecil/Debby...).

    Requirements:
      - Send a packet EVERY frame (lifetick watchdog).
      - Lifetick should advance globally; we use CommandFrame.tick & 0xFFFF.
      - PLC tracks following error => on enable rising edge: PosSoll := last PosIst.
    """

    axis_id: str
    remote: Tuple[str, int]          # (plc_ip, plc_port) e.g. ("172.16.17.1", 15001)
    local: Tuple[str, int]           # (controller_ip, local_port) e.g. ("172.16.17.5", 15001)

    timeout_s: float = 0.02
    codec: TwinCATLegacyWinchCodec = field(default_factory=TwinCATLegacyWinchCodec)

    # session/ownership
    own_pid: str = field(default_factory=lambda: str(os.getpid()))
    control_pid_tx: int = 0
    intent: bool = True

    # legacy knobs (explicit)
    modus: str = "E"
    guide_control_ui: int = 0
    guide_soll_speed: float = 0.0
    estop_reset: int = 0
    resync: float = 0.0
    gui_not_halt: int = 0

    _sock: Optional[socket.socket] = None

    # PosSoll integrator + edge detect + last telemetry
    _pos_soll: float = 0.0
    _last_pos_ist: float = 0.0
    _last_enable: bool = False

    def _ensure_sock(self) -> socket.socket:
        if self._sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(self.timeout_s)
            # Bind per-axis local port on controller (per your ACHSEN mapping)
            s.bind(self.local)
            self._sock = s
        return self._sock

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def step(self, state, cmd, dt: float) -> None:
        sock = self._ensure_sock()

        # Always ensure the axis exists and we can store telemetry
        ax = state.ensure_axis(self.axis_id)
        ax.kind = "legacy_twincat"

    # Default setpoint if axis not present in cmd.axes
        sp = getattr(cmd, "axes", {}).get(self.axis_id)

        if sp is None:
            enable_cmd = False
            vel_cmd = 0.0
        else:
            enable_cmd = bool(sp.enable)
            vel_cmd = float(sp.vel)

        # Lifetick must be present EVERY frame; make it deterministic:
        lifetick = int(getattr(cmd, "tick", 0)) & 0xFFFF

        # Apply global safety gating AFTER reading the command
        enable = enable_cmd and (not state.estop) and (not state.fault)
        vel = vel_cmd if enable else 0.0

       # rising edge detect (after gating)
        rebased = enable and (not self._last_enable)

        if rebased:
            # Load integrator with last known PosIst (following-error friendly)
            self._pos_soll = float(ax.pos)
        elif enable:
            # Integrate only when enabled and not on rebase tick
            self._pos_soll += vel * float(dt)

        self._last_enable = enable

        # Minimal placeholder ControlIN (refine later once we confirm bitfield)
        control_in = 1 if enable else 0

        down = TwinCATLegacyWinchDownlink(
            lifetick=lifetick,
            modus=self.modus,
            own_pid=self.own_pid,
            control_pid_tx=int(self.control_pid_tx),
            intent=bool(self.intent),
            control_in=int(control_in),
            guide_control_ui=int(self.guide_control_ui),
            speed_soll=float(vel),
            guide_soll_speed=float(self.guide_soll_speed),
            pos_soll=float(self._pos_soll),
            estop_reset=int(self.estop_reset),
            resync=float(self.resync),
            gui_not_halt=int(self.gui_not_halt),
            write_params=None,
        )

        # Always send every frame
        sock.sendto(self.codec.encode_downlink(down).encode("utf-8"), self.remote)

        # Receive telemetry (best effort)
        try:
            data, _addr = sock.recvfrom(65535)
        except socket.timeout:
            return
        except ConnectionResetError:
            # Windows: ICMP Port Unreachable -> WSAECONNRESET on recvfrom
            return
        except OSError as e:
            # also common on Windows: WSAECONNRESET = 10054
            if getattr(e, "winerror", None) == 10054:
                return
            raise

        txt = data.decode("utf-8", errors="replace").strip()
        if not txt:
            return

        up = self.codec.decode_uplink(txt)
        f = up.fields

        # --- parse measured basics (common surface) ---
        pos_ist = float(parse_float(f.get("PosIst", "0"), default=ax.pos))
        vel_ist = float(parse_float(f.get("SpeedIstUI", "0"), default=ax.vel))

        status_word = int(parse_int(f.get("Status", "0"), default=0))
        estop_status = int(parse_int(f.get("EStopStatus", "0"), default=0))

        # Heuristic from ST: Status == 4356 treated as "ready"
        STATUS_READY = 4356
        estop_active = (estop_status != 0)
        enabled_meas = (not estop_active) and (status_word == STATUS_READY)

        # IMPORTANT: do NOT treat status_word != 0 as a fault.
        # Until we decode a real fault bit, keep this conservative:
        fault_active = False

        # --- write common surface (for logging/UI/TelemetrySnapshot) ---
        ax.pos = pos_ist
        ax.vel = vel_ist
        ax.enabled = enabled_meas
        ax.fault = fault_active

        # --- axis kind + full legacy telemetry blob (Step 2 design rule) ---
        ax.tel = LegacyAxisTelemetry(
            link_ok=True,
            name=self.axis_id,
            # keys may differ by codec; keep safe defaults if missing
            own_pid_rx=str(f.get("OwnPID", "")),
            lifetick_tx=int(parse_int(f.get("LifetickUItx", "0"), default=0)),
            status_word=status_word,
            guide_status_word=int(parse_int(f.get("GuideStatus", "0"), default=0)),
            estop_status_dword=estop_status,
            system_time=str(f.get("SystemTime", "")),

            pos_ist=pos_ist,
            vel_ist=vel_ist,

            estop_active=estop_active,
            fault_active=fault_active,
            enabled=enabled_meas,
        )

        # --- keep commanded intent visible for debugging (meta only) ---
        ax.meta["cmd_enable"] = bool(enable)
        ax.meta["cmd_vel"] = float(vel)
        ax.meta["status_word"] = status_word
        ax.meta["estop_status"] = estop_status
        ax.meta["own_pid_tx"] = self.own_pid

        # cache for next enable edge (following-error friendly)
        self._last_pos_ist = pos_ist

