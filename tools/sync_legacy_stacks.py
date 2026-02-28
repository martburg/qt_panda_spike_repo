# tools/sync_legacy_stacks.py
"""Sync legacy configs/stacks mirrors from configs/profiles.

This repo has moved to `configs/profiles/*.toml` as the source of truth.
`configs/stacks/*.toml` remains as a compatibility mirror for older docs/scripts.

Run this script after changing profiles to keep the mirror in sync:

    python tools/sync_legacy_stacks.py
"""

from __future__ import annotations

import shutil
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    profiles_dir = repo_root / "configs" / "profiles"
    stacks_dir = repo_root / "configs" / "stacks"

    stacks_dir.mkdir(parents=True, exist_ok=True)

    profiles = sorted(p for p in profiles_dir.glob("*.toml") if p.is_file())
    profile_names = {p.name for p in profiles}

    # Copy/overwrite mirrors
    for prof in profiles:
        dst = stacks_dir / prof.name
        shutil.copyfile(prof, dst)

    # Remove stale mirrors
    for stale in stacks_dir.glob("*.toml"):
        if stale.name not in profile_names:
            stale.unlink()

    print(f"[legacy-stacks] synced {len(profiles)} profile(s) -> configs/stacks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
