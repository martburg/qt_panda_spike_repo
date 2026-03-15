from __future__ import annotations

from steuerung3d.protocol.legacy_plc import encode_uplink
from steuerung3d.protocol.plc_codec_uplink_support import decode_snapshot_from_payload


def test_decode_snapshot_carries_livetick_diff_from_geartoui() -> None:
    payload = encode_uplink(
        fields={
            "LifetickUItx": 1235,
            "GearToUI": 1200,
            "Name": "Anton",
            "PosIst": "12.34",
            "SpeedIstUI": "1.25",
        },
        tail={"SystemTime": "N_2026-01-12-09:20:31.123"},
    ).encode("utf-8")
    snap = decode_snapshot_from_payload(payload)
    assert snap is not None
    ax = snap.axes["Anton"]
    assert ax.device_tick == 1235
    assert ax.lifetick_rx == 1200
    assert ax.lifetick_age == 35
