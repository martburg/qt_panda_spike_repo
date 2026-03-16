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
from typing import Any, Dict, List, Mapping, Optional, Tuple

from steuerung3d.adapters.links.udp_link import UdpLink
from steuerung3d.protocol.parse_primitives import parse_bool, parse_float

_PARAM_GROUP_DEFAULTS: Dict[str, List[str]] = {
    "pos": ["HardMax", "UserMax", "UserMin", "HardMin", "PosWin"],
    "vel": ["VelMax", "VelWin", "AccMax", "AccMove", "DccMax", "MaxAmp", "VelMaxMot"],
    "filter": ["P", "I", "D", "IL", "RampForm"],
    "guider": ["PosMax", "PosMin", "Pitch"],
}


def _axis_id_or_default(axis_id: Optional[str], default: str = "X") -> str:
    value = str(axis_id or default).strip()
    return value or default


def _frame_axis_id(frame: Any, default: str = "X") -> str:
    try:
        axes = getattr(frame, "axes", {}) or {}
    except Exception:
        return default
    if isinstance(axes, Mapping) and axes:
        try:
            return _axis_id_or_default(str(next(iter(axes.keys()))), default)
        except Exception:
            return default
    return default


def _frame_lifetick_ui_rx(frame: Any, axis_id: str) -> int:
    try:
        echo = getattr(frame, "lifetick_echo", {}) or {}
    except Exception:
        return 0
    if isinstance(echo, Mapping) and axis_id in echo:
        try:
            return int(echo[axis_id])
        except Exception:
            return 0
    return 0


def _extract_param_write_values(
    fields: Mapping[str, object],
    *,
    group_defaults: Mapping[str, List[str]],
    param_keymap: Mapping[str, str],
) -> List[tuple[str, Dict[str, float]]]:
    out: List[tuple[str, Dict[str, float]]] = []
    for grp, keys in group_defaults.items():
        values: Dict[str, float] = {}
        for key in keys:
            plc_key = param_keymap.get(key)
            if not plc_key or plc_key not in fields:
                continue
            values[str(key)] = _to_float(fields.get(plc_key, "0"), 0.0)
        if values:
            out.append((str(grp), values))
    return out


def _frame_param_map(frame: Any) -> Dict[str, float]:
    params: Dict[str, float] = {}
    try:
        from steuerung3d.core.command_frame import ParamWriteOp, coerce_param_ops

        for op in coerce_param_ops(getattr(frame, "param_ops", []) or []):
            if not isinstance(op, ParamWriteOp):
                continue
            for key, value in dict(op.values or {}).items():
                try:
                    params[str(key)] = float(value)
                except Exception:
                    continue
    except Exception:
        return {}
    return params


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


def _to_int(x: object, default: int = 0) -> int:
    """Tolerant int conversion for PLC tokens (accepts '1', '1.0', etc.)."""
    try:
        return int(float(str(x).strip()))
    except Exception:
        return int(default)


def _to_float(x: object, default: float = 0.0) -> float:
    """Tolerant float conversion for PLC tokens."""
    return float(parse_float(x, default=default))


def _to_bool_token(x: object, default: bool = False) -> bool:
    """Parse legacy PLC-ish booleans.

    ST truth (KommAnton__MAIN.st):
      - `Intent` is compared against the *string* 'True' (case-sensitive).
      - Other on-wire flags are typically numeric (WORD/INT/DWORD) where non-zero means true.

    Policy here:
      - empty token => False (even if default=True) (matches previous behavior)
      - accept a broad token set (true/false/on/off/1/0/...) via :func:`parse_bool`
      - accept numeric-ish tokens as well (e.g. DWORD bitfields): non-zero => True
    """
    try:
        s = str(x).strip()
    except Exception:
        return bool(default)
    if s == "":
        return False

    sl = s.lower()

    # First accept the centralized token set (1/0, true/false, on/off, ...).
    v = parse_bool(s, default=default)
    if sl in ("1", "0", "true", "false", "t", "f", "yes", "no", "y", "n", "on", "off"):
        return bool(v)

    # Then accept legacy numeric-ish tokens as well (e.g. DWORD bitfields): non-zero => True.
    try:
        return int(sl, 10) != 0
    except Exception:
        try:
            return float(sl) != 0.0
        except Exception:
            return bool(default)


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

        axis_id = _axis_id_or_default(self.axis_id)

        for raw in self.link.poll(limit=limit):
            try:
                dec = decode_downlink(raw)
                if dec is None:
                    continue
                fields = dec.fields or {}
                if not isinstance(fields, dict):
                    continue

                tick_ui_rx = _to_int(fields.get("LifetickUIrx", "0"), 0)
                vel = _to_float(fields.get("SpeedSollIN", "0"), 0.0)

                enable = _to_bool_token(fields.get("ControlIN", "False"), False)
                intent = _to_bool_token(fields.get("Intent", "True"), True)
                resync = _to_bool_token(fields.get("ReSync", "False"), False)
                gui_not_halt = _to_bool_token(fields.get("GUINotHaltIN", "False"), False)

                param_ops: List[Any] = []
                modus = str(fields.get("Modus", "") or "").strip().lower()
                if modus == "w":
                    for group, values in _extract_param_write_values(
                        fields,
                        group_defaults=_PARAM_GROUP_DEFAULTS,
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
                    estop_reset=_to_bool_token(fields.get("EStopReset", "False"), False),
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

        axis_id = _frame_axis_id(frame)
        lifetick_ui_rx = _frame_lifetick_ui_rx(frame, axis_id)
        params = _frame_param_map(frame)

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
