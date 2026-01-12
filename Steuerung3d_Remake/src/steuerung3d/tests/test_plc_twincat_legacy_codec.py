from __future__ import annotations

from steuerung3d.adapters.plc_twincat_legacy.codec import (
    TwinCATLegacyWinchCodec,
    TwinCATLegacyWinchDownlink,
)


def test_downlink_order_and_trailing_sep():
    c = TwinCATLegacyWinchCodec()
    d = TwinCATLegacyWinchDownlink(
        lifetick=123,
        modus="E",
        own_pid="9999",
        control_pid_tx=0,
        intent=True,
        control_in=1,
        guide_control_ui=0,
        speed_soll=1.5,
        guide_soll_speed=0.0,
        pos_soll=42.0,
        estop_reset=0,
        resync=0.0,
        gui_not_halt=0,
        write_params=None,
    )

    line = c.encode_downlink(d)
    assert line.endswith(";")

    parts = [p for p in line.split(";") if p != ""]
    assert parts[0] == "123"      # LifetickUIrx
    assert parts[1] == "E"        # Modus
    assert parts[2] == "9999"     # OwnPID
    assert parts[4] == "True"     # Intent string
    assert parts[7] == "1.5"      # SpeedSollIN
    assert parts[9] == "42.0"     # PosSoll


def test_uplink_eod_split_tail_fields():
    c = TwinCATLegacyWinchCodec()

    # minimal prefix up to EStopStatus (38 fields) then EOD then 7 tail fields
    prefix = [
        "9999",  # OwnPID
        "10",    # LifetickUItx
        "0",     # Status
        "0",     # GuideStatus
        "1.23",  # PosIst
        "2.34",  # SpeedIstUI
        "0", "0", "Anton", "1.0",
        "0","0","0","0","0","0","0","0",
        "0","0","0","0","0","0","0","0","0",
        "0","0","0","0","0","0","0","0",
        "0",
        "0","0", # RampenformUI, EStopStatus
    ]
    assert len(prefix) == 38

    tail = ["N_2026-01-12T10:00:00", "1.0", "2.0", "0.1", "0.2", "0.3", "9.9"]

    line = ";".join(prefix + ["EOD"] + tail) + ";"
    up = c.decode_uplink(line)

    assert up.fields["PosIst"] == "1.23"
    assert up.fields["SpeedIstUI"] == "2.34"
    assert up.tail["SystemTime"].startswith("N_")
    assert up.tail["GuidePosManualMaxUI"] == "9.9"
