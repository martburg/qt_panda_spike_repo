# tools/check_legacy_stacks.py
"""Ensure legacy configs/stacks mirrors configs/profiles.

We keep `configs/stacks/*.toml` only for backward compatibility (older docs/scripts).
To avoid drift, treat `configs/profiles/*.toml` as the source of truth and enforce
that stacks are exact copies.

If you need to refresh the mirror, run:

    python tools/sync_legacy_stacks.py
"""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    profiles_dir = repo_root / "configs" / "profiles"
    stacks_dir = repo_root / "configs" / "stacks"

    if not profiles_dir.exists():
        print(f"[legacy-stacks] no profiles dir: {profiles_dir}")
        return 2

    if not stacks_dir.exists():
        print(f"[legacy-stacks] no stacks dir: {stacks_dir}")
        return 2

    profiles = sorted(p for p in profiles_dir.glob("*.toml") if p.is_file())
    stacks = {p.name: p for p in stacks_dir.glob("*.toml") if p.is_file()}

    errors: list[str] = []

    for prof in profiles:
        mirror = stacks.get(prof.name)
        if mirror is None:
            errors.append(f"missing mirror: configs/stacks/{prof.name}")
            continue
        if prof.read_text(encoding="utf-8") != mirror.read_text(encoding="utf-8"):
            errors.append(
                f"drift: configs/stacks/{prof.name} differs from configs/profiles/{prof.name}"
            )

    extra = sorted(set(stacks.keys()) - {p.name for p in profiles})
    for name in extra:
        # Keep this strict: extra files are almost always stale copies.
        errors.append(f"stale mirror (no corresponding profile): configs/stacks/{name}")

    if errors:
        print("[legacy-stacks] FAIL")
        print(
            "[legacy-stacks] configs/profiles/*.toml is authoritative; configs/stacks/*.toml is a strict compatibility mirror."
        )
        print(
            "[legacy-stacks] Do not edit configs/stacks directly. Edit configs/profiles and then refresh the mirror."
        )
        for e in errors:
            print(" -", e)
        print("\n[legacy-stacks] Refresh mirror with: python tools/sync_legacy_stacks.py")
        return 1

    print(f"[legacy-stacks] OK ({len(profiles)} mirrored profiles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
