r"""UDP channels for legacy TwinCAT semicolon-delimited PLC frames.

These are intentionally *not* JSON. They carry plain ASCII lines like:

    0;20400;0;0;0.0;...;Anton;...;EOD\;...

The canonical field order is defined in :mod:`steuerung3d.protocol.legacy_plc`.

Design goal here: provide a *thin* transport wrapper around :class:`~steuerung3d.adapters.links.udp_link.UdpLink`,
and expose methods that match the rest of the stack (``publish_command_frame`` / ``drain_telemetry`` etc.).

We keep everything best-effort and defensive: these channels are used for debugging and bring-up, so
we prefer “don’t crash” over “strict schema enforcement”.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from steuerung3d.adapters.links.udp_link import UdpLink
from steuerung3d.protocol.udp_plc_coerce import to_bool_token, to_float, to_int
from steuerung3d.protocol.udp_plc_frame_support import (
    PARAM_GROUP_DEFAULTS,
    axis_id_or_default,
    extract_param_write_values,
    frame_axis_id,
    frame_lifetick_ui_rx,
    frame_param_map,
)


def _to_bytes(line: str) -> bytes:
    # PLC traffic is ASCII-ish. Keep it permissive.
    if not line.endswith(";"):
        line = line + ";"
    return line.encode("utf-8", errors="replace")


def _from_bytes(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").strip("\x00\r\n ")


@dataclass
class UdpPlcTelemetryIn:
    link: UdpLink

    @staticmethod
    def bind(addr: Tuple[str, int]) -> "UdpPlcTelemetryIn":
        # target unused for rx
        return UdpPlcTelemetryIn(link=UdpLink(bind=addr, target=addr))

    def drain_lines(self, limit: int = 1000) -> List[str]:
        return [_from_bytes(b) for b in self.link.poll(limit=limit)]

    def drain_telemetry(self, limit: int = 100) -> List[Any]:
        """Drain and decode PLC uplink telegrams into TelemetrySnapshot objects."""
        out: List[Any] = []
        try:
            from steuerung3d.protocol.plc_codec import decode_uplink_to_snapshot
        except Exception:
            decode_uplink_to_snapshot = None  # type: ignore

        for raw in self.link.poll(limit=limit):
            if decode_uplink_to_snapshot is None:
                continue
            try:
                snap = decode_uplink_to_snapshot(raw)
                if snap is not None:
                    out.append(snap)
            except Exception:
                continue
        return out


@dataclass
class UdpPlcTelemetryOut:
    link: UdpLink

    @staticmethod
    def connect(
        target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpPlcTelemetryOut":
        return UdpPlcTelemetryOut(link=UdpLink(bind=bind, target=target))

    def publish_line(self, line: str) -> None:
        self.link.send(_to_bytes(line))

    def publish_telemetry(self, payload: Any) -> None:
        """Publish telemetry on the PLC wire.

        Accepts either:
          - a pre-serialized PLC telemetry line (str)
          - a TelemetrySnapshot-like object (has .axes)
          - a list/tuple of lines or snapshots
        """
        if payload is None:
            return

        # Batch handling
        if isinstance(payload, (list, tuple)):
            if not payload:
                return
            if all(isinstance(x, str) for x in payload):
                for line in payload:
                    self.publish_line(line)
                return
            payload = payload[0]

        if isinstance(payload, str):
            self.publish_line(payload)
            return

        # Snapshot-like: use the existing conservative encoder.
        try:
            from steuerung3d.protocol.plc_wire import encode_plc_telemetry

            line = encode_plc_telemetry(payload)
            self.publish_line(line)
        except Exception:
            self.publish_line(str(payload))


@dataclass
class UdpPlcCommandIn:
    link: UdpLink
    axis_id: Optional[str] = None

    @staticmethod
    def bind(addr: Tuple[str, int], axis_id: Optional[str] = None) -> "UdpPlcCommandIn":
        return UdpPlcCommandIn(link=UdpLink(bind=addr, target=addr), axis_id=axis_id)

    def drain_lines(self, limit: int = 1000) -> List[str]:
        return [_from_bytes(b) for b in self.link.poll(limit=limit)]

    def drain_command_frames(self, limit: int = 100) -> List[Any]:
        """Drain and decode PLC downlink telegrams into CommandFrame objects.

        The PLC downlink does not contain the axis name; we therefore bind the
        channel to a specific axis via ``axis_id`` (DenSi is usually single-axis).

        ST semantics:
        - Modus == 'w' means the write-extension fields are present (parameter write).
        - Intent, EStopReset, ReSync, GUINotHaltIN are boolean *string* tokens in ST ('True'/'False')
          and the ST often compares case-sensitively against 'True'.
        - ControlIN is effectively a numeric enable/bitfield; we accept tolerant boolean parsing.
        """
        out: List[Any] = []
        try:
            from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, ParamWriteOp
            from steuerung3d.protocol.plc_codec import _PARAM_KEYMAP, decode_downlink
        except Exception:
            return out

        axis_id = axis_id_or_default(self.axis_id)

        for raw in self.link.poll(limit=limit):
            try:
                dec = decode_downlink(raw)
                if dec is None:
                    continue
                fields = dec.fields or {}
                if not isinstance(fields, dict):
                    continue

                tick_ui_rx = to_int(fields.get("LifetickUIrx", "0"), 0)
                vel = to_float(fields.get("SpeedSollIN", "0"), 0.0)

                enable = to_bool_token(fields.get("ControlIN", "False"), False)
                intent = to_bool_token(fields.get("Intent", "True"), True)
                resync = to_bool_token(fields.get("ReSync", "False"), False)
                gui_not_halt = to_bool_token(fields.get("GUINotHaltIN", "False"), False)

                param_ops: List[Any] = []
                modus = str(fields.get("Modus", "") or "").strip().lower()
                if modus == "w":
                    for group, values in extract_param_write_values(
                        fields,
                        group_defaults=PARAM_GROUP_DEFAULTS,
                        param_keymap=_PARAM_KEYMAP,
                    ):
                        param_ops.append(ParamWriteOp(group=group, values=values))

                cmd = CommandFrame(
                    tick=tick_ui_rx,
                    t_s=0.0,
                    estop=False,
                    fault=False,
                    core_mode=str(fields.get("CoreMode", "")) or "",
                    axes={axis_id: AxisSetpoint(enable=enable, vel=vel)},
                    intent=bool(intent),
                    resync=bool(resync),
                    gui_not_halt=bool(gui_not_halt),
                    estop_reset=to_bool_token(fields.get("EStopReset", "False"), False),
                    lifetick_echo={axis_id: tick_ui_rx},
                    resync_by_axis={axis_id: bool(resync)} if bool(resync) else {},
                    param_ops=param_ops,
                )
                out.append(cmd)
            except Exception:
                continue

        return out


@dataclass
class UdpPlcCommandOut:
    link: UdpLink

    @staticmethod
    def connect(
        target: Tuple[str, int], *, bind: Tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpPlcCommandOut":
        return UdpPlcCommandOut(link=UdpLink(bind=bind, target=target))

    def publish_line(self, line: str) -> None:
        self.link.send(_to_bytes(line))

    def publish_command_frame(self, frame: Any) -> None:
        """Encode a CommandFrame and send it as a PLC downlink telegram."""
        try:
            from steuerung3d.protocol.plc_codec import encode_downlink
        except Exception:
            encode_downlink = None  # type: ignore

        if encode_downlink is None:
            # best-effort: stringify
            self.publish_line(str(frame))
            return

        axis_id = frame_axis_id(frame)
        lifetick_ui_rx = frame_lifetick_ui_rx(frame, axis_id)
        params = frame_param_map(frame)

        try:
            payload = encode_downlink(
                axis_id=axis_id,
                frame=frame,
                pid=str(os.getpid()),
                lifetick_ui_rx=int(lifetick_ui_rx),
                params=params or None,
            )
            self.link.send(payload)
        except Exception:
            # last resort: stringify
            self.publish_line(str(frame))
