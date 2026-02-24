from __future__ import annotations

from pathlib import Path

from steuerung3d.core.stack_loader import load_stack_profile


def test_1dev_sim_profile_uses_core_udp_service() -> None:
    """Protect the canonical core entrypoint used by the dev_sim profile."""

    repo_root = Path(__file__).resolve().parents[1]
    profile = repo_root / "configs" / "stacks" / "1dev_sim.toml"
    spec = load_stack_profile(profile, base_dir=repo_root)

    core = spec.services.get("core")
    assert core is not None
    assert core.module == "steuerung3d.apps.core_udp_service"
