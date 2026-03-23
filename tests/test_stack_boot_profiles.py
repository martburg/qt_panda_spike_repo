from __future__ import annotations

from pathlib import Path

import pytest

from steuerung3d.apps.supervisor.profile_loader import load_profile as load_supervisor_profile
from steuerung3d.core.stack_loader import load_stack_profile
from steuerung3d.core.stack_runtime import expand_processes


def test_dev_sim_profile_loads_and_expands(tmp_path: Path):
    profile = Path("configs/profiles/dev_sim.toml")
    spec = load_stack_profile(profile)
    assert spec.name == "dev_sim"
    assert spec.axes == ["Anton", "Debby", "Cecil", "Burt"]

    procs = expand_processes(spec, session_dir=tmp_path)
    names = [p.name for p in procs]

    # Start-order heuristic: core first, densis, hip, inputd, joy2intent.
    assert names[0] == "core"
    assert "hip" in names
    assert "inputd" in names
    assert "joy2intent" in names

    # Per-axis fanout
    assert "densi-Anton" in names
    assert "densi-Debby" in names
    assert "densi-Cecil" in names
    assert "densi-Burt" in names

    # Verify cmd ports are computed correctly for per-axis densis.
    densi_anton = next(p for p in procs if p.name == "densi-Anton")
    assert "--cmd-in" in densi_anton.argv
    cmd_in = densi_anton.argv[densi_anton.argv.index("--cmd-in") + 1]
    assert cmd_in.endswith(":52001")

    densi_burt = next(p for p in procs if p.name == "densi-Burt")
    cmd_in_b = densi_burt.argv[densi_burt.argv.index("--cmd-in") + 1]
    assert cmd_in_b.endswith(":52004")


def test_profile_missing_axes_is_error(tmp_path: Path):
    bad = tmp_path / "bad.toml"
    bad.write_text(
        """
[stack]
name = "bad"

[services.core]
enabled = true
module = "steuerung3d.apps.core_udp_service"
args = []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_stack_profile(bad)


def test_override_toml_rewrites_ports(tmp_path: Path):
    """Override TOML should take precedence over base for scalar fields."""
    profile = Path("configs/profiles/dev_sim.toml")
    ov = tmp_path / "override.toml"
    ov.write_text(
        """
[net]
cmd_base = 53001
""",
        encoding="utf-8",
    )
    spec = load_stack_profile(profile, overrides=[ov])
    procs = expand_processes(spec, session_dir=tmp_path)
    densi_anton = next(p for p in procs if p.name == "densi-Anton")
    cmd_in = densi_anton.argv[densi_anton.argv.index("--cmd-in") + 1]
    assert cmd_in.endswith(":53001")


def test_set_disables_service(tmp_path: Path):
    profile = Path("configs/profiles/dev_sim.toml")
    spec = load_stack_profile(profile, sets=["services.hip.enabled=false"])
    procs = expand_processes(spec, session_dir=tmp_path)
    names = [p.name for p in procs]
    assert "hip" not in names


def test_two_dev_two_hip_attach_profile_loads_and_expands(tmp_path: Path):
    profile = Path("configs/profiles/2dev_2hip_attach_sim.toml")
    spec = load_stack_profile(profile)
    assert spec.name == "2dev_2hip_attach_sim"
    assert spec.axes == ["Anton", "Debby"]

    procs = expand_processes(spec, session_dir=tmp_path)
    names = [p.name for p in procs]

    assert "core" in names
    assert "densi-Anton" in names
    assert "densi-Debby" in names
    assert "hip-1" in names
    assert "hip-2" in names
    assert "inputd" not in names
    assert "joy2intent" not in names

    hip1 = next(p for p in procs if p.name == "hip-1")
    hip2 = next(p for p in procs if p.name == "hip-2")

    assert hip1.argv[hip1.argv.index("--telem-in") + 1].endswith(":51002")
    assert hip2.argv[hip2.argv.index("--telem-in") + 1].endswith(":51003")
    assert hip1.argv[hip1.argv.index("--hip-id") + 1] == "hip-1"
    assert hip2.argv[hip2.argv.index("--hip-id") + 1] == "hip-2"

    core = next(p for p in procs if p.name == "core")
    assert core.argv[core.argv.index("--ui-telem-mode") + 1] == "fanout"


def test_supervisor_stack_standard_profile_keeps_densi_headless(tmp_path: Path):
    profile = Path("configs/profiles/supervisor_2axes_core_fanout.toml")
    spec = load_stack_profile(profile)
    procs = expand_processes(spec, session_dir=tmp_path)

    densi_anton = next(p for p in procs if p.name == "densi-Anton")
    assert "--headless" in densi_anton.argv


def test_supervisor_stack_debug_profile_opens_visible_densi(tmp_path: Path):
    profile = Path("configs/profiles/supervisor_2axes_core_fanout_debug.toml")
    spec = load_stack_profile(profile)
    procs = expand_processes(spec, session_dir=tmp_path)

    densi_anton = next(p for p in procs if p.name == "densi-Anton")
    assert "--headless" not in densi_anton.argv


def test_supervisor_smoke_motion_profile_swaps_inputd_for_inputd_sim(tmp_path: Path) -> None:
    profile = Path("configs/profiles/supervisor_2axes_core_fanout_smoke_motion.toml")
    spec = load_stack_profile(profile)
    procs = expand_processes(spec, session_dir=tmp_path)
    names = [p.name for p in procs]

    assert "inputd" not in names
    assert "inputd_sim" in names
    assert "joy2intent" in names

    inputd_sim = next(p for p in procs if p.name == "inputd_sim")
    assert "--config" in inputd_sim.argv
    cfg_path = inputd_sim.argv[inputd_sim.argv.index("--config") + 1]
    assert cfg_path.endswith("configs/services/inputd_sim_smoke.toml")


def test_two_axis_head_non_vertical_all_in_one_profile_includes_supervisor(tmp_path: Path) -> None:
    profile = Path("configs/profiles/two_axis_head_non_vertical_all_in_one.toml")
    spec = load_stack_profile(profile)
    assert spec.name == "two_axis_head_non_vertical_all_in_one"
    assert spec.axes == ["HeadJoint1", "HeadJoint2"]

    procs = expand_processes(spec, session_dir=tmp_path)
    names = [p.name for p in procs]

    assert "core" in names
    assert "densi-HeadJoint1" in names
    assert "densi-HeadJoint2" in names
    assert "inputd" in names
    assert "joy2intent" in names
    assert "supervisor" in names

    supervisor = next(p for p in procs if p.name == "supervisor")
    assert (
        supervisor.argv[0].endswith("python")
        or supervisor.argv[0].endswith("python3")
        or "python" in supervisor.argv[0].lower()
    )
    assert supervisor.argv[1:5] == ["-m", "steuerung3d", "sup", "--profile"]

    supervisor_profile = Path(supervisor.argv[5])
    assert supervisor_profile.name == "smoke_two_axis_head_non_vertical_embedded.toml"

    sup_cfg = load_supervisor_profile(supervisor_profile)
    assert not sup_cfg.launch_stack
