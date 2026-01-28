from __future__ import annotations

from steuerung3d.protocol.legacy_plc import parse_uplink


def test_parse_uplink_extracts_base_and_tail_fields():
    # Minimal synthetic message following the documented structure:
    base = [
        "4711",  # OwnPID
        "1235",  # LifetickUItx
        "0",  # Status
        "0",  # GuideStatus
        "12.34000",  # PosIst
        "1.25000",  # SpeedIstUI
        "0.00000",  # MasterMomentUI
        "34.2",  # CabTemperatureUI
        "Anton",  # Name
    ]
    # pad remaining base fields to 38 tokens
    while len(base) < 38:
        base.append("0")

    tail = [
        "N_2026-01-12-09:20:31.123",
        "12.34000",
        "1.25000",
        "0.50000",
        "0.50000",
        "5.000",
        "0.096",
    ]
    line = ";".join(base + ["EOD"] + tail) + ";"

    u = parse_uplink(line)

    assert u.fields["OwnPID"] == "4711"
    assert u.fields["Name"] == "Anton"
    assert u.fields["PosIst"] == "12.34000"
    assert u.tail["SystemTime"].startswith("N_2026-01-12")
    assert u.tail["AccTotUI"] == "5.000"
