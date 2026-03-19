from __future__ import annotations

from steuerung3d.apps.hi_p.smoke_control import (
    HiPSmokeCommand,
    decode_hip_smoke_command,
    encode_hip_smoke_command,
)


def test_hip_smoke_command_roundtrip_preserves_group_and_values() -> None:
    cmd = HiPSmokeCommand(action="edit_write", group="vel", values={"VelMax": 1.75})

    payload = encode_hip_smoke_command(cmd)
    decoded = decode_hip_smoke_command(payload)

    assert decoded.action == "edit_write"
    assert decoded.group == "vel"
    assert decoded.values == {"VelMax": 1.75}
