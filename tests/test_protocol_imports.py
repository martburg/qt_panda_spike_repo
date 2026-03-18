from steuerung3d.protocol.codec import decode_raw_controls, encode_raw_controls
from steuerung3d.protocol.raw_controls import RawControls


def test_udp_channels_import_smoke() -> None:
    """Refactor tripwire: importing udp_channels must never fail."""
    import importlib

    module = importlib.import_module("steuerung3d.protocol.udp_channels")
    assert module.__name__ == "steuerung3d.protocol.udp_channels"


def test_raw_controls_codec_roundtrip():
    rc = RawControls(
        type="raw_controls",
        t_ns=123,
        src="pytest",
        axes=[-1.0, 0.0, 1.0],
        buttons=[0, 1, 0, 1],
    )

    payload = encode_raw_controls(rc)
    rc2 = decode_raw_controls(payload)

    assert rc2.type == rc.type
    assert rc2.t_ns == rc.t_ns
    assert rc2.src == rc.src
    assert rc2.axes == rc.axes
    assert rc2.buttons == rc.buttons
