from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Optional, Tuple

from steuerung3d.adapters.plc.line_codec import PlcLineCodec, parse_bool, parse_float, parse_int
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState


@dataclass
class UdpPlcDevice:
    """Device adapter that speaks a simple semicolon-separated UDP protocol.

    This is the *device boundary* for CoreEngine.device_step.

    It sends one line per axis in the command frame and applies the first
    received telemetry line per axis to `state.axes[axis_id]`.

    Notes:
      - v0.1 is intentionally minimal (single outstanding request).
      - The real Beckhoff layout has more fields; the codec is schema-driven.
    """

    remote: Tuple[str, int] = ("127.0.0.1", 55001)
    timeout_s: float = 0.02
    codec: PlcLineCodec = field(default_factory=lambda: PlcLineCodec())    
    _sock: Optional[socket.socket] = None

    def _ensure_sock(self) -> socket.socket:
        if self._sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(self.timeout_s)
            self._sock = s
        return self._sock

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def step(self, state: MachineState, cmd: CommandFrame, dt: float) -> None:
        sock = self._ensure_sock()

        # Encode setpoints
        out_lines = []
        tick = int(state.tick)
        for axis_id, sp in cmd.axes.items():
            out_lines.append(
                self.codec.encode_rx(
                    {
                        "tick": tick,
                        "axis": axis_id,
                        "enable": 1 if sp.enable else 0,
                        "vel": sp.vel,
                    }
                )
            )

        if not out_lines:
            return

        payload = "\n".join(out_lines).encode("utf-8")
        sock.sendto(payload, self.remote)

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

        txt = data.decode("utf-8", errors="replace")
        for ln in txt.replace("\r", "\n").split("\n"):
            ln = ln.strip()
            if not ln:
                continue
            tx = self.codec.decode_tx(ln)
            axis = tx.get("axis")
            if not axis:
                continue
            # Discovery: create axes on first sight so HiPs can select them.
            ax = state.ensure_axis(str(axis))
            # Record last-seen (core tick) for UI/health decisions.
            ax.meta["last_seen_tick"] = int(state.tick)
            ax.enabled = bool(parse_bool(tx.get("enabled", "0")))
            ax.vel = float(parse_float(tx.get("vel", "0")))
            ax.pos = float(parse_float(tx.get("pos", "0")))
            # fault is optional
            fault = parse_int(tx.get("fault", "0"), default=0)
            ax.fault = fault != 0
