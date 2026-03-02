"""Unified entry point for booting Steuerung3D stacks.

Primary commands:
  python -m steuerung3d up --profile dev_sim
  python -m steuerung3d plan --profile dev_sim
  python -m steuerung3d status --profile dev_sim
  python -m steuerung3d down --profile dev_sim
  python -m steuerung3d logs core --profile dev_sim --follow
  python -m steuerung3d doctor --profile dev_sim
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .commands import (
    cmd_doctor,
    cmd_down,
    cmd_logs,
    cmd_plan,
    cmd_profiles,
    cmd_status,
    cmd_up,
    discover_stack_profiles,
)


def _profile_arg(value: str) -> str:
    """argparse type for --profile.

    Accepts either:
      - a known profile name (resolved via configs/profiles/<name>.toml; legacy: configs/stacks)
      - an explicit TOML path

    Raises a helpful error listing known profile names.
    """
    v = (value or "").strip()
    if not v:
        raise argparse.ArgumentTypeError("empty profile")
    p = Path(v)
    if p.exists() or p.suffix.lower() == ".toml":
        return v
    names = discover_stack_profiles()
    if v in names:
        return v
    if names:
        sample = ", ".join(names[:12])
        more = " …" if len(names) > 12 else ""
        raise argparse.ArgumentTypeError(
            f"unknown profile '{v}'. Available: {sample}{more}. "
            "(Tip: run `python -m steuerung3d profiles`)"
        )
    raise argparse.ArgumentTypeError(
        f"unknown profile '{v}' and no profiles discovered. "
        "(Tip: expected configs/profiles/*.toml (or legacy configs/stacks) or a direct .toml path)"
    )


class St3DArgumentParser(argparse.ArgumentParser):
    """ArgumentParser with nicer errors for missing/unknown profiles."""

    def error(self, message: str) -> None:  # type: ignore[override]
        extra = ""
        if "--profile" in message:
            names = discover_stack_profiles()
            if names:
                extra_lines = [
                    "",
                    "Available profiles (configs/profiles/*.toml; legacy configs/stacks):",
                ]
                extra_lines += [f"  - {n}" for n in names]
                extra_lines += ["", "Tip: python -m steuerung3d profiles"]
                extra = "\n".join(extra_lines) + "\n"
            else:
                extra = (
                    "\nNo profiles found under configs/profiles/ (or legacy configs/stacks/). "
                    "Provide a direct .toml path, or add configs/profiles/<name>.toml.\n"
                )

        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{extra}")


def build_parser() -> argparse.ArgumentParser:
    p = St3DArgumentParser(prog="python -m steuerung3d")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("profiles", help="list available stack profiles")
    sp.add_argument("--dir", default=None, help="override profiles dir (default: configs/profiles)")
    sp.add_argument("--paths", action="store_true", help="print full paths")
    sp.set_defaults(_fn=cmd_profiles)

    def add_profile_args(pp: argparse.ArgumentParser, *, with_overrides: bool = True) -> None:
        pp.add_argument("--profile", required=True, type=_profile_arg)
        if with_overrides:
            pp.add_argument("--override", action="append", default=[], help="override TOML key=val")
            pp.add_argument("--set", action="append", default=[], help="set TOML dotted.path=val")

    sp = sub.add_parser("up", help="start stack and run forever")
    add_profile_args(sp, with_overrides=True)
    sp.add_argument("--keep-last-sessions", type=int, default=3)
    sp.add_argument("--new-console", action="store_true")
    sp.set_defaults(_fn=cmd_up)

    sp = sub.add_parser("plan", help="print the process plan (argv + logs)")
    add_profile_args(sp, with_overrides=True)
    sp.set_defaults(_fn=cmd_plan)

    sp = sub.add_parser("status", help="show status of last session")
    add_profile_args(sp, with_overrides=False)
    sp.set_defaults(_fn=cmd_status)

    sp = sub.add_parser("down", help="terminate last session processes")
    add_profile_args(sp, with_overrides=False)
    sp.set_defaults(_fn=cmd_down)

    sp = sub.add_parser("logs", help="print or follow logs")
    add_profile_args(sp, with_overrides=False)
    sp.add_argument("service")
    sp.add_argument("--follow", action="store_true")
    sp.set_defaults(_fn=cmd_logs)

    sp = sub.add_parser("doctor", help="sanity check a profile")
    add_profile_args(sp, with_overrides=True)
    sp.set_defaults(_fn=cmd_doctor)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    fn = getattr(ns, "_fn", None)
    if not fn:
        return 2
    return int(fn(ns))


if __name__ == "__main__":
    raise SystemExit(main())
