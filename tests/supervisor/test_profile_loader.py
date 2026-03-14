from __future__ import annotations

from pathlib import Path

import pytest

from steuerung3d.apps.supervisor.profile_loader import load_profile


def test_load_profile_parses_pairs(tmp_path: Path) -> None:
    p = tmp_path / "sup.toml"
    p.write_text(
        """
[supervisor]
id = "sup_main"
title = "Main Supervisor"
cycle_ms = 60
telem_in = "127.0.0.1:51002"
intent_out = "127.0.0.1:51001"

[[pairs]]
pair_id = "anton"
axis_id = "Anton"
densi_id = "Anton"
hip_id = "hip_anton"
selected = true
densi_action_out = "127.0.0.1:53001"
""",
        encoding="utf-8",
    )
    prof = load_profile(p)
    assert prof.supervisor_id == "sup_main"
    assert prof.title == "Main Supervisor"
    assert prof.pairs[0].pair_id == "anton"
    assert prof.pairs[0].densi_action_out == "127.0.0.1:53001"


def test_load_profile_rejects_duplicate_pair_ids(tmp_path: Path) -> None:
    p = tmp_path / "sup.toml"
    p.write_text(
        """
[supervisor]
id = "sup_main"

[[pairs]]
pair_id = "anton"
axis_id = "Anton"

[[pairs]]
pair_id = "anton"
axis_id = "Debby"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate supervisor pair_id"):
        load_profile(p)


def test_load_profile_rejects_duplicate_axis_ids(tmp_path: Path) -> None:
    p = tmp_path / "sup.toml"
    p.write_text(
        """
[supervisor]
id = "sup_main"

[[pairs]]
pair_id = "anton"
axis_id = "Anton"

[[pairs]]
pair_id = "debby"
axis_id = "Anton"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate supervisor axis_id"):
        load_profile(p)
