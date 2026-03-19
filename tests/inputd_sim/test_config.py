from __future__ import annotations

from pathlib import Path

import pytest

from steuerung3d.apps.inputd_sim.config import (
    PreparedInputdSimScenario,
    interpolate_axes,
    load_inputd_sim_config,
    prepare_scenario,
)


def _write_configs(tmp_path: Path) -> Path:
    scenario_dir = tmp_path / "configs" / "inputd_sim"
    services_dir = tmp_path / "configs" / "services"
    scenario_dir.mkdir(parents=True)
    services_dir.mkdir(parents=True)

    scenario = scenario_dir / "scenario.toml"
    scenario.write_text(
        """
[aliases.axes]
manual = 1
trim = 2

[aliases.buttons]
deadman = 5
aux = 7

[[steps]]
name = "neutral"
hold_s = 0.25

[[steps]]
name = "drive"
hold_s = 1.0
ramp_s = 0.2

[steps.axes]
manual = 0.30
"2" = -0.10

[steps.buttons]
deadman = true
aux = true

[[steps]]
name = "release"
hold_s = 0.50

[steps.axes]
manual = 0.0

[steps.buttons]
deadman = false
aux = false
""",
        encoding="utf-8",
    )

    cfg = services_dir / "inputd_sim.toml"
    cfg.write_text(
        """
[io]
out = "127.0.0.1:50100"
tick_hz = 60

[control]
bind = "127.0.0.1:50101"
autostart = false

[input]
num_axes = 8
num_buttons = 16
default_axis = 0.0
default_button = false
src = "inputd_sim_test"

[scenario]
path = "../inputd_sim/scenario.toml"
""",
        encoding="utf-8",
    )
    return cfg


def test_load_inputd_sim_config_supports_aliases_and_raw_indices(tmp_path: Path) -> None:
    cfg = load_inputd_sim_config(_write_configs(tmp_path))

    assert cfg.out_addr == ("127.0.0.1", 50100)
    assert cfg.control_in_addr == ("127.0.0.1", 50101)
    assert cfg.tick_hz == 60.0
    assert cfg.src == "inputd_sim_test"
    assert cfg.scenario.axis_aliases == {"manual": 1, "trim": 2}
    assert cfg.scenario.button_aliases == {"deadman": 5, "aux": 7}
    assert len(cfg.scenario.steps) == 3
    assert cfg.scenario.steps[1].axis_targets == {1: 0.30, 2: -0.10}
    assert cfg.scenario.steps[1].button_targets == {5: True, 7: True}


def test_prepare_scenario_persists_omitted_values_between_steps(tmp_path: Path) -> None:
    cfg = load_inputd_sim_config(_write_configs(tmp_path))

    prepared = prepare_scenario(cfg)

    assert isinstance(prepared, PreparedInputdSimScenario)
    assert prepared.initial_axes == (0.0,) * 8
    assert prepared.steps[1].target_axes[1] == 0.30
    assert prepared.steps[1].target_axes[2] == -0.10
    assert prepared.steps[2].target_axes[1] == 0.0
    assert prepared.steps[2].target_axes[2] == -0.10
    assert prepared.steps[1].target_buttons[5] == 1
    assert prepared.steps[2].target_buttons[5] == 0


def test_interpolate_axes_ramps_linearly() -> None:
    axes = interpolate_axes((0.0, -1.0), (1.0, 1.0), elapsed_s=0.1, ramp_s=0.2)

    assert len(axes) == 2
    assert abs(axes[0] - 0.5) < 1e-9
    assert abs(axes[1] - 0.0) < 1e-9


def test_load_inputd_sim_config_rejects_out_of_range_axis_value(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "configs" / "inputd_sim"
    services_dir = tmp_path / "configs" / "services"
    scenario_dir.mkdir(parents=True)
    services_dir.mkdir(parents=True)
    (scenario_dir / "bad.toml").write_text(
        """
[[steps]]
name = "bad"
hold_s = 0.1

[steps.axes]
"0" = 1.5
""",
        encoding="utf-8",
    )
    cfg = services_dir / "bad_inputd_sim.toml"
    cfg.write_text(
        """
[input]
num_axes = 2
num_buttons = 2
default_axis = 0.0
default_button = false
src = "bad"

[scenario]
path = "../inputd_sim/bad.toml"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="axes.0 out of range"):
        load_inputd_sim_config(cfg)
