from __future__ import annotations

import pytest

from steuerung3d.adapters.plc.line_codec import PlcLineCodec, PlcLineSchema


def test_codec_strips_trailing_sep() -> None:
    c = PlcLineCodec()
    rx = c.decode_rx("12;X;1;0.5;\n")
    assert rx["tick"] == "12"
    assert rx["axis"] == "X"
    assert rx["enable"] == "1"
    assert rx["vel"] == "0.5"


def test_codec_roundtrip_custom_schema() -> None:
    c = PlcLineCodec(
        rx=PlcLineSchema(("axis", "tick", "vel", "enable")),
        tx=PlcLineSchema(("axis", "tick", "pos")),
    )

    line = c.encode_rx({"axis": "Y", "tick": 7, "vel": 1.25, "enable": 0})
    assert line.startswith("Y;7;1.25;0")

    got = c.decode_rx(line)
    assert got == {"axis": "Y", "tick": "7", "vel": "1.25", "enable": "0"}


def test_codec_missing_field_raises() -> None:
    c = PlcLineCodec()
    with pytest.raises(KeyError):
        c.encode_rx({"tick": 1, "axis": "X", "enable": 1})
