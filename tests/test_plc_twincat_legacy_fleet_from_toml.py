from __future__ import annotations

from pathlib import Path

from steuerung3d.adapters.plc_twincat_legacy.udp_sim import build_udp_sim_fleet_from_toml
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.core.state import MachineState


def _find_repo_root(start: Path) -> Path:
    p = start.resolve()
    for parent in (p, *p.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    raise AssertionError(f"Could not find repo root (pyproject.toml) from {start}")


def test_fleet_from_repo_toml_steps_all_axes_and_updates_measured_state():
    repo_root = _find_repo_root(Path(__file__))
    cfg_path = repo_root / "configs" / "dev_plc.toml"
    assert cfg_path.exists(), f"Missing config: {cfg_path}"

    bundle = build_udp_sim_fleet_from_toml(cfg_path, dt_s=0.01)
    try:
        st = MachineState()

        # Axis IDs come from TOML; make sure we see all four after stepping.
        axis_ids = ["Anton", "Burt", "Cecil", "Debby"]

        # Step a few frames with per-axis velocities so we can detect fan-out.
        for k in range(5):
            cmd = CommandFrame(
                tick=100 + k,
                t_s=0.01 * k,
                estop=False,
                fault=False,
                mode="LIVE",
                axes={
                    "Anton": AxisSetpoint(enable=True, vel=0.6),
                    "Burt": AxisSetpoint(enable=True, vel=0.7),
                    "Cecil": AxisSetpoint(enable=True, vel=0.8),
                    "Debby": AxisSetpoint(enable=True, vel=0.9),
                },
            )
            bundle.step(st, cmd, dt=0.01)

        # Assert: every axis exists and has updated measured values
        for aid in axis_ids:
            assert aid in st.axes, f"{aid} missing from MachineState.axes"
            ax = st.axes[aid]
            assert ax.pos != 0.0, f"{aid} pos did not change"
            assert ax.vel != 0.0, f"{aid} vel did not change"

            # "one truth" policy: enabled must be PLC-reported (SIM emits Status=4356 when enabled)
            assert ax.enabled is True, f"{aid} not enabled per PLC/SIM report"
    finally:
        bundle.close()
