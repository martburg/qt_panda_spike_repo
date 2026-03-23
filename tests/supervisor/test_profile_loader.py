from __future__ import annotations

from pathlib import Path

import pytest

from steuerung3d.apps.supervisor.profile_loader import load_profile


def test_load_profile_parses_axes(tmp_path: Path) -> None:
    p = tmp_path / "sup.toml"
    p.write_text(
        """
[supervisor]
id = "sup_main"
title = "Main Supervisor"
cycle_ms = 60
telem_in = "127.0.0.1:51002"
intent_out = "127.0.0.1:51001"

[[axes]]
unit_id = "anton"
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
    assert prof.axes[0].unit_id == "anton"
    assert prof.axes[0].densi_action_out == "127.0.0.1:53001"
    assert prof.axes[0].unit_id == "anton"


def test_load_profile_parses_multiple_axes(tmp_path: Path) -> None:
    p = tmp_path / "sup.toml"
    p.write_text(
        """
[supervisor]
id = "sup_main"

[[axes]]
unit_id = "anton"
axis_id = "Anton"
selected = true

[[axes]]
unit_id = "debby"
axis_id = "Debby"
selected = false
""",
        encoding="utf-8",
    )
    prof = load_profile(p)
    assert [axis.unit_id for axis in prof.axes] == ["anton", "debby"]
    assert [axis.axis_id for axis in prof.axes] == ["Anton", "Debby"]


def test_load_profile_parses_legacy_pairs(tmp_path: Path) -> None:
    p = tmp_path / "sup.toml"
    p.write_text(
        """
[supervisor]
id = "sup_main"

[[pairs]]
pair_id = "anton"
axis_id = "Anton"
selected = true
""",
        encoding="utf-8",
    )
    prof = load_profile(p)
    assert prof.axes[0].unit_id == "anton"
    assert prof.axes[0].axis_id == "Anton"
    assert prof.pairs[0].pair_id == "anton"


def test_load_profile_rejects_duplicate_unit_ids_from_legacy_pairs(tmp_path: Path) -> None:
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
    with pytest.raises(ValueError, match="duplicate supervisor unit_id"):
        load_profile(p)


def test_load_profile_rejects_duplicate_axis_ids(tmp_path: Path) -> None:
    p = tmp_path / "sup.toml"
    p.write_text(
        """
[supervisor]
id = "sup_main"

[[axes]]
unit_id = "anton"
axis_id = "Anton"

[[axes]]
unit_id = "debby"
axis_id = "Anton"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate supervisor axis_id"):
        load_profile(p)


def test_load_profile_parses_two_axis_head_kinematics(tmp_path: Path) -> None:
    p = tmp_path / "sup.toml"
    p.write_text(
        """
[supervisor]
id = "sup_main"

[[axes]]
unit_id = "pan"
axis_id = "Pan"

[[axes]]
unit_id = "tilt"
axis_id = "Tilt"

[kinematics]
kind = "two_axis_head"
joint1_max_rate_deg_s = 120
joint2_max_rate_deg_s = 60
joint1_axis_base_xyz = [0.0, 1.0, 0.0]
joint2_axis_joint1_xyz = [0.0, 0.0, 1.0]
tool_forward_xyz = [1.0, 0.0, 0.0]

[kinematics.axes]
joint1_axis_id = "Pan"
joint2_axis_id = "Tilt"
""",
        encoding="utf-8",
    )
    prof = load_profile(p)
    assert prof.kinematics is not None
    assert prof.kinematics.joint1_axis_id == "Pan"
    assert prof.kinematics.joint2_axis_id == "Tilt"
    assert prof.kinematics.joint1_max_rate_deg_s == 120.0
    assert prof.kinematics.joint2_max_rate_deg_s == 60.0
    assert prof.kinematics.joint1_axis_base_xyz == (0.0, 1.0, 0.0)
    assert prof.kinematics.joint2_axis_joint1_xyz == (0.0, 0.0, 1.0)
    assert prof.kinematics.tool_forward_xyz == (1.0, 0.0, 0.0)


def test_load_profile_parses_two_axis_head_control_map(tmp_path: Path) -> None:
    p = tmp_path / "sup_control_map.toml"
    p.write_text(
        """
[supervisor]
id = "sup_main"

[[axes]]
unit_id = "pan"
axis_id = "Pan"

[[axes]]
unit_id = "tilt"
axis_id = "Tilt"

[kinematics]
kind = "two_axis_head"

[kinematics.axes]
joint1_axis_id = "Pan"
joint2_axis_id = "Tilt"

[kinematics.control_map]
joint1 = "look_tilt"
joint2 = "look_pan"
""",
        encoding="utf-8",
    )
    prof = load_profile(p)
    assert prof.kinematics_control_map is not None
    assert prof.kinematics_control_map.joint1_channel == "look_tilt"
    assert prof.kinematics_control_map.joint2_channel == "look_pan"


def test_load_profile_rejects_legacy_pan_tilt_aliases(tmp_path: Path) -> None:
    p = tmp_path / "sup_legacy.toml"
    p.write_text(
        """
[supervisor]
id = "sup_main"

[[axes]]
unit_id = "pan"
axis_id = "Pan"

[[axes]]
unit_id = "tilt"
axis_id = "Tilt"

[kinematics.pan_tilt]
pan_axis_id = "Pan"
tilt_axis_id = "Tilt"
pan_max_rate_deg_s = 120
tilt_max_rate_deg_s = 60
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="pan_tilt aliases were removed"):
        load_profile(p)


def test_load_profile_smoke_two_axis_head_non_vertical_file() -> None:
    prof = load_profile(Path("configs/supervisor/smoke_two_axis_head_non_vertical.toml"))
    assert prof.launch_stack == "configs/profiles/two_axis_head_non_vertical_debug.toml"
    assert tuple(axis.axis_id for axis in prof.axes) == ("HeadJoint1", "HeadJoint2")
    assert tuple(axis.densi_action_out for axis in prof.axes) == (
        "127.0.0.1:53001",
        "127.0.0.1:53002",
    )
    assert prof.kinematics is not None
    assert prof.kinematics.machine_id == "head_non_vertical_a"


def test_load_profile_example_two_axis_head_non_vertical_file() -> None:
    prof = load_profile(Path("configs/supervisor/example_two_axis_head_non_vertical.toml"))
    assert prof.kinematics is not None
    assert prof.kinematics.machine_id == "head_non_vertical_a"
    assert prof.kinematics.joint1_axis_base_xyz == (0.0, 1.0, 0.0)
    assert prof.kinematics.joint2_axis_joint1_xyz == (0.0, 0.0, 1.0)
    assert prof.kinematics.base_origin_xyz == (0.0, 0.0, 1.2)
    assert prof.kinematics_control_map is not None
    assert prof.kinematics_control_map.joint1_channel == "look_pan"
    assert prof.kinematics_control_map.joint2_channel == "look_tilt"
