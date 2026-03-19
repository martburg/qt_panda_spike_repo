from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from steuerung3d.protocol.udp_channels import UdpJsonIn, UdpJsonOut
from steuerung3d.protocol.udp_link_scaffold import bind_udp_link, connect_udp_link

InputdSimControlAction = Literal["start", "restart", "idle"]


@dataclass(frozen=True)
class InputdSimControl:
    type: str = "inputd_sim_control"
    action: InputdSimControlAction = "start"


def encode_inputd_sim_control(command: InputdSimControl) -> dict[str, object]:
    return {"type": command.type, "action": command.action}


def decode_inputd_sim_control(payload: dict[str, object]) -> InputdSimControl:
    raw_action = str(payload.get("action", "start") or "start").strip().lower()
    action: InputdSimControlAction
    if raw_action == "restart":
        action = "restart"
    elif raw_action == "idle":
        action = "idle"
    else:
        action = "start"
    return InputdSimControl(action=action)


@dataclass
class UdpInputdSimControlIn:
    rx: UdpJsonIn[InputdSimControl]

    @staticmethod
    def bind(addr: tuple[str, int]) -> "UdpInputdSimControlIn":
        link = bind_udp_link(addr)
        return UdpInputdSimControlIn(rx=UdpJsonIn(link=link, decode=decode_inputd_sim_control))

    def drain_commands(self, limit: int = 1000) -> list[InputdSimControl]:
        return self.rx.drain(limit=limit)


@dataclass
class UdpInputdSimControlOut:
    tx: UdpJsonOut[InputdSimControl]

    @staticmethod
    def connect(
        target: tuple[str, int], *, bind: tuple[str, int] = ("127.0.0.1", 0)
    ) -> "UdpInputdSimControlOut":
        link = connect_udp_link(target, bind=bind)
        return UdpInputdSimControlOut(tx=UdpJsonOut(link=link, encode=encode_inputd_sim_control))

    def publish_command(self, command: InputdSimControl) -> None:
        self.tx.send(command)
