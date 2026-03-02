from __future__ import annotations

from steuerung3d.protocol.plc_codec import decode_downlink


def _st_bool_token(x: str | None, default: bool = False) -> bool:
    """ST-truthy boolean token interpretation.

    ST truth (KommAnton__MAIN.st):
      - Some fields are literal string tokens: 'True' / 'False' (case-sensitive in ST compares)
      - Some fields are numeric words/bitfields: 0 means false, non-zero means true.
    """
    if x is None:
        return default
    s = str(x).strip()
    if s == "":
        return False  # legacy behavior used in downlink parsing: missing/empty -> False
    sl = s.lower()
    if sl in ("true", "t", "yes", "y", "on"):
        return True
    if sl in ("false", "f", "no", "n", "off"):
        return False
    # Numeric truthiness (bitfields etc.)
    try:
        return int(float(s)) != 0
    except Exception:
        return default


def test_plc_downlink_parses_true_false_tokens_st_truth() -> None:
    # Token order is defined in plc_codec_fields.DOWNLINK_BASE_FIELDS:
    # LifetickUIrx; Modus; OwnPID; ControlPIDTx; Intent; ControlIN; GuideControlUI;
    # SpeedSollIN; GuideSollSpeedUI; PosSoll; EStopReset; ReSync; GUINotHaltIN;
    raw = b"1234;E;4711;0;True;0;0;1.25;0;0;True;False;True;"
    dec = decode_downlink(raw)
    assert dec is not None, "decode_downlink should parse a valid base downlink telegram"

    f = dec.fields

    # ST truth: Intent/EStopReset/ReSync/GUINotHaltIN are boolean *string* tokens.
    assert _st_bool_token(f.get("Intent"), default=True) is True
    assert _st_bool_token(f.get("EStopReset"), default=False) is True
    assert _st_bool_token(f.get("ReSync"), default=False) is False
    assert _st_bool_token(f.get("GUINotHaltIN"), default=False) is True

    # ST truth: ControlIN is numeric bitfield; bit0 enable. Here: 0 => disabled.
    assert _st_bool_token(f.get("ControlIN"), default=False) is False


def test_plc_downlink_missing_estop_reset_defaults_false_st_truth() -> None:
    # Missing EStopReset token should default to False (legacy behavior),
    # while ControlIN remains numeric.
    raw = b"1234;E;4711;0;True;0;0;1.25;0;0;;False;False;"
    dec = decode_downlink(raw)
    assert dec is not None, "decode_downlink should parse a valid base downlink telegram"

    f = dec.fields

    # Empty EStopReset -> False
    assert _st_bool_token(f.get("EStopReset"), default=False) is False

    # Still parse other tokens normally
    assert _st_bool_token(f.get("Intent"), default=True) is True
    assert _st_bool_token(f.get("ReSync"), default=False) is False
    assert _st_bool_token(f.get("GUINotHaltIN"), default=False) is False
    assert _st_bool_token(f.get("ControlIN"), default=False) is False
