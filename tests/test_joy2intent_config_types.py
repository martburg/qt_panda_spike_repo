from __future__ import annotations

from pathlib import Path

import pytest

from steuerung3d.apps.joy2intent.config import load_joy2intent_config


def _write_cfg(path: Path, *, tick_hz: str = "50.0") -> Path:
    text = f"""
[io]
raw_in = "127.0.0.1:5001"
intent_out = "127.0.0.1:5002"
context_in = "127.0.0.1:5003"
tick_hz = {tick_hz}
stale_after_ms = 200

[identity]
hip_id = "hip-test"

[rig]
winches = ["Anton", "Debby"]
select_buttons = [0, 1]

[mode]
default = "manual"
publish_local_manual = false

[limits.manual]
max_winch_mps = 1.25
fine_scale = 0.5

[limits.sync.max_v]
Anton = 0.9

[bindings.axes]
manual_jog = 1

[bindings.buttons]
deadman = 5
select = [0, 1]

[filters]
deadzone = 0.05
expo = 1.5

[filters.invert]
manual_jog = false
"""
    path.write_text(text, encoding="utf-8")
    return path


def test_load_joy2intent_config_keeps_expected_types(tmp_path: Path) -> None:
    cfg = load_joy2intent_config(_write_cfg(tmp_path / "joy.toml"))

    assert cfg.raw_in == ("127.0.0.1", 5001)
    assert cfg.intent_out == ("127.0.0.1", 5002)
    assert cfg.context_in == ("127.0.0.1", 5003)
    assert cfg.tick_hz == 50.0
    assert cfg.stale_after_ms == 200
    assert cfg.winches == ["Anton", "Debby"]
    assert cfg.select_buttons == [0, 1]
    assert cfg.publish_local_manual is False
    assert cfg.axes == {"manual_jog": 1}
    assert cfg.buttons == {"deadman": 5, "select": [0, 1]}
    assert cfg.invert == {"manual_jog": False}
    assert cfg.sync_max_v == {"Anton": 0.9}


def test_load_joy2intent_config_rejects_wrong_numeric_type(tmp_path: Path) -> None:
    path = _write_cfg(tmp_path / "joy_bad.toml", tick_hz='"fast"')
    with pytest.raises(ValueError, match="io.tick_hz"):
        load_joy2intent_config(path)
