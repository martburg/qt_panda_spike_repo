from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from steuerung3d.adapters.links.udp_link import UdpLink
from steuerung3d.protocol.udp_channels import UdpJsonIn, UdpJsonOut


def _empty_float_dict() -> dict[str, float]:
    return {}


@dataclass(frozen=True)
class HiPSmokeCommand:
    type: str = "hip_smoke_command"
    action: str = "edit"
    group: str = ""
    values: dict[str, float] = field(default_factory=_empty_float_dict)


def encode_hip_smoke_command(command: HiPSmokeCommand) -> dict[str, Any]:
    return {
        "type": command.type,
        "action": str(command.action),
        "group": str(command.group),
        "values": {str(k): float(v) for k, v in dict(command.values or {}).items()},
    }


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except Exception:
            return None
    return None


def decode_hip_smoke_command(payload: dict[str, object]) -> HiPSmokeCommand:
    raw_values_obj: object = payload.get("values")
    values: dict[str, float] = {}
    if isinstance(raw_values_obj, dict):
        raw_map = cast(dict[object, object], raw_values_obj)
        for key_obj, value_obj in raw_map.items():
            value = _coerce_float(value_obj)
            if value is None:
                continue
            values[str(key_obj)] = value
    return HiPSmokeCommand(
        action=str(payload.get("action", "edit") or "edit"),
        group=str(payload.get("group", "") or ""),
        values=values,
    )


@dataclass
class UdpHiPSmokeControlIn:
    rx: UdpJsonIn[HiPSmokeCommand]

    @staticmethod
    def bind(addr: tuple[str, int]) -> "UdpHiPSmokeControlIn":
        link = UdpLink(bind=addr, target=addr)
        return UdpHiPSmokeControlIn(rx=UdpJsonIn(link=link, decode=decode_hip_smoke_command))

    def drain_commands(self, limit: int = 1000) -> list[HiPSmokeCommand]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpHiPSmokeControlOut:
    tx: UdpJsonOut[HiPSmokeCommand]

    @staticmethod
    def connect(
        target: tuple[str, int], *, bind: tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpHiPSmokeControlOut":
        link = UdpLink(bind=bind, target=target)
        return UdpHiPSmokeControlOut(tx=UdpJsonOut(link=link, encode=encode_hip_smoke_command))

    def publish_command(self, command: HiPSmokeCommand) -> None:
        self.tx.send(command)
