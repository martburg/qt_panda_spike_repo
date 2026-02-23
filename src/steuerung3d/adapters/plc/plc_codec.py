from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, List

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot, AxisTelemetry

from .plc_config import PlcWireSpec


@dataclass
class PlcCodec:
    """
    PLC codec: bytes <-> typed objects.

    This is where "what the PLC strings mean" lives.
    Transport (UDP sockets etc.) is handled elsewhere.

    Command TX placeholder format (semicolon-delimited, newline-terminated):
      tick;estop;fault;mode;X_enable;X_vel;Y_enable;Y_vel;...

    Telemetry RX placeholder format (semicolon-delimited, newline optional):
      tick;t_s;mode;estop;fault;X_pos;X_vel;X_enabled;X_fault;Y_pos;Y_vel;Y_enabled;Y_fault;...

    IMPORTANT:
      The telemetry layout above is a *scaffold*. Replace/extend try_decode_telemetry()
      to match the real PLC stream once we finalize the field map.
    """

    spec: PlcWireSpec

    # -----------------------
    # TX: core -> PLC
    # -----------------------
    def encode_command_frame(self, cmd: CommandFrame) -> bytes:
        d = self.spec.delimiter
        parts: List[str] = [
            str(int(cmd.tick)),
            self.spec.true_token if cmd.estop else self.spec.false_token,
            self.spec.true_token if cmd.fault else self.spec.false_token,
            str(cmd.mode),
        ]

        for axis_id in self.spec.axis_ids:
            sp = cmd.axes.get(axis_id)
            if sp is None:
                en = False
                vel = 0.0
            else:
                en = bool(sp.enable)
                vel = float(sp.vel)

            parts.append(self.spec.true_token if en else self.spec.false_token)
            parts.append(self.spec.float_fmt.format(vel))

        line = d.join(parts) + "\n"
        return line.encode(self.spec.encoding, errors="strict")

    # -----------------------
    # RX: PLC -> core
    # -----------------------
    def try_decode_telemetry(self, payload: bytes) -> Optional[TelemetrySnapshot]:
        """
        Best-effort parse.
        Returns None on parse errors so the caller can ignore bad packets.
        """
        try:
            text = payload.decode(self.spec.encoding, errors="strict").strip()
            if not text:
                return None

            parts = text.split(self.spec.delimiter)

            # Header fields
            # tick;t_s;mode;estop;fault;...
            if len(parts) < 5:
                return None

            tick = int(parts[0])
            t_s = float(parts[1])
            mode = str(parts[2])
            estop = (parts[3] == self.spec.true_token)
            fault = (parts[4] == self.spec.true_token)

            # Per-axis fields:
            # X_pos;X_vel;X_enabled;X_fault; repeated
            idx = 5
            axes_out: Dict[str, AxisTelemetry] = {}
            for axis_id in self.spec.axis_ids:
                if idx + 4 > len(parts):
                    return None
                pos = float(parts[idx + 0])
                vel = float(parts[idx + 1])
                enabled = (parts[idx + 2] == self.spec.true_token)
                ax_fault = (parts[idx + 3] == self.spec.true_token)
                axes_out[axis_id] = AxisTelemetry(
                    pos=pos,
                    vel=vel,
                    enabled=enabled,
                    fault=ax_fault,
                )
                idx += 4

            return TelemetrySnapshot(
                tick=tick,
                t_s=t_s,
                mode=mode,
                core_mode=mode,
                estop=estop,
                fault=fault,
                axes=axes_out,
            )
        except Exception:
            return None
