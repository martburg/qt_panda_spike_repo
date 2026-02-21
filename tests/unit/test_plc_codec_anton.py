from __future__ import annotations

from steuerung3d.protocol.legacy_plc import UPLINK_BASE_FIELDS, UPLINK_TAIL_FIELDS, parse_uplink
from steuerung3d.protocol.plc_codec import decode_downlink
from steuerung3d.protocol.plc_wire import encode_plc_telemetry
from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot


def test_decode_downlink_base_fields() -> None:
    line = "1234;E;4711;0;True;0;0;1.25000;0.00000;12.34000;0;0;0;"
    dec = decode_downlink(line.encode("utf-8"))
    assert dec is not None
    assert dec.is_write is False
    assert dec.fields.get("SpeedSollIN") == "1.25000"
    assert dec.fields.get("PosSoll") == "12.34000"


def test_decode_downlink_write_extension_fields() -> None:
    line = (
        "1234;w;4711;0;True;0;0;1.25000;0.00000;12.34000;0;0;0;"
        "5;4;300;300;0;0;2.5;5;5;100;1;0;0;1;-6.3;0.096;0;VEL;0.5;0.5;5;"
    )
    dec = decode_downlink(line.encode("utf-8"))
    assert dec is not None
    assert dec.is_write is True
    assert dec.fields.get("FilterP") == "1"
    assert dec.fields.get("AccTotUI") == "5"


def test_encode_plc_uplink_has_eod_and_tail() -> None:
    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.1,
        mode="IDLE",
        estop=False,
        fault=False,
        axes={"Anton": AxisTelemetry(pos=1.0, vel=2.0, enabled=True, fault=False)},
    )
    line = encode_plc_telemetry(snap)
    toks = [t for t in line.split(";") if t != ""]
    assert "EOD\\" in toks

    parsed = parse_uplink(line)
    assert len(parsed.fields) == len(UPLINK_BASE_FIELDS)
    assert len(parsed.tail) == len(UPLINK_TAIL_FIELDS)
