from __future__ import annotations

import socket

from steuerung3d.protocol.udp_plc_channels import UdpPlcCommandIn


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def test_udp_plc_command_in_parses_true_false_tokens() -> None:
    port = _free_port()
    rx = UdpPlcCommandIn.bind(("127.0.0.1", port), axis_id="Anton")

    line = "1234;E;4711;0;True;False;0;1.25;0;0;True;False;True;"

    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.sendto(line.encode("utf-8"), ("127.0.0.1", port))
    tx.close()

    cmds = rx.drain_command_frames(limit=10)
    assert cmds, "Expected at least one decoded CommandFrame"

    cmd = cmds[0]
    axis = cmd.axes["Anton"]
    assert axis.enable is False
    assert cmd.intent is True
    assert cmd.resync is False
    assert cmd.gui_not_halt is True
    assert cmd.estop_reset is True


def test_udp_plc_command_missing_estop_reset_defaults_false() -> None:
    port = _free_port()
    rx = UdpPlcCommandIn.bind(("127.0.0.1", port), axis_id="Anton")

    line = "1234;E;4711;0;True;False;0;1.25;0;0;;False;False;"

    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.sendto(line.encode("utf-8"), ("127.0.0.1", port))
    tx.close()

    cmds = rx.drain_command_frames(limit=10)
    assert cmds, "Expected at least one decoded CommandFrame"

    cmd = cmds[0]
    assert cmd.estop_reset is False
