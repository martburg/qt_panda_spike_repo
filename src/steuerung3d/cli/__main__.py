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
import os
import re
import signal
import sys
import time
from pathlib import Path

from steuerung3d.core.stack_meta import find_latest_session_dir, load_meta
from steuerung3d.core.stack_runtime import expand_processes

from steuerung3d.core.stack_loader import load_stack_profile
from steuerung3d.core.stack_runtime import StackRuntime


def discover_stack_profiles(stacks_dir: Path | None = None) -> list[str]:
    """Return available stack profile *names* (without .toml).

    We intentionally keep this lightweight and file-system based.
    A profile can still be provided as an explicit TOML path.
    """
    d = stacks_dir or (Path("configs") / "stacks")
    if not d.exists() or not d.is_dir():
        return []
    out: list[str] = []
    for p in sorted(d.glob("*.toml")):
        if p.is_file():
            out.append(p.stem)
    return out


def _print_profiles(stacks_dir: Path | None = None, *, as_paths: bool = False) -> None:
    names = discover_stack_profiles(stacks_dir)
    d = stacks_dir or (Path("configs") / "stacks")
    if not names:
        print(f"[profiles] none found (looked in {d})")
        return
    print(f"[profiles] available ({len(names)}) in {d}:")
    for n in names:
        if as_paths:
            print(f"- {d / (n + '.toml')}")
        else:
            print(f"- {n}")


def _profile_arg(value: str) -> str:
    """argparse type for --profile.

    Accepts either:
      - a known profile name (resolved via configs/stacks/<name>.toml)
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
        "(Tip: expected configs/stacks/*.toml or a direct .toml path)"
    )


class St3DArgumentParser(argparse.ArgumentParser):
    """ArgumentParser with nicer errors for missing/unknown profiles."""

    def error(self, message: str) -> None:  # type: ignore[override]
        # Custom error path so we can append profile discovery hints.
        extra = ""
        if "--profile" in message:
            names = discover_stack_profiles()
            if names:
                extra_lines = ["", "Available profiles (configs/stacks/*.toml):"]
                extra_lines += [f"  - {n}" for n in names]
                extra_lines += ["", "Tip: python -m steuerung3d profiles"]
                extra = "\n".join(extra_lines) + "\n"
            else:
                extra = (
                    "\nNo profiles found under configs/stacks/. "
                    "Provide a direct .toml path, or add configs/stacks/<name>.toml.\n"
                )

        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{extra}")


def cmd_profiles(args: argparse.Namespace) -> int:
    # Keep the behavior minimal and script-friendly.
    stacks_dir = Path(args.dir) if getattr(args, "dir", None) else None
    _print_profiles(stacks_dir=stacks_dir, as_paths=bool(args.paths))
    return 0


def _stack_run_base(name: str) -> Path:
    return Path(".run") / name


def _default_profile_path(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.suffix.lower() == ".toml" or p.exists():
        return p
    # name -> configs/stacks/<name>.toml
    return Path("configs") / "stacks" / f"{name_or_path}.toml"


def cmd_up(args: argparse.Namespace) -> int:
    profile = _default_profile_path(args.profile)
    spec = load_stack_profile(profile, overrides=args.override, sets=args.set)
    rt = StackRuntime(spec, keep_last_sessions=args.keep_last_sessions, new_console=bool(args.new_console))
    session_dir = rt.start()
    print(f"[stack] started: {spec.name} (session {session_dir})")
    return rt.run_forever()


def cmd_plan(args: argparse.Namespace) -> int:
    profile = _default_profile_path(args.profile)
    spec = load_stack_profile(profile, overrides=args.override, sets=args.set)
    # Use a temporary session dir name (not created) for stable log path previews.
    session_dir = _stack_run_base(spec.name) / "sessions" / "PLAN"
    plan = expand_processes(spec, session_dir=session_dir)
    for p in plan:
        print(f"- {p.name}")
        print(f"    log: {p.log_path}")
        print(f"    argv: {' '.join(p.argv)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    profile = _default_profile_path(args.profile)
    spec = load_stack_profile(profile)
    base = _stack_run_base(spec.name)
    session = find_latest_session_dir(base)
    if not session:
        print(f"[status] no sessions found in {base}")
        return 1
    meta = load_meta(session)
    alive = meta.is_running()
    state = "RUNNING" if alive else "STOPPED"
    print(f"[status] {meta.stack_name}: {state} (session {session})")
    for name, c in meta.children.items():
        is_up = "up" if (alive and c.pid and _pid_alive(c.pid)) else "down"
        print(f"  - {name:<16} pid={c.pid:<6} {is_up} rc={c.returncode}")
    return 0 if alive else 2


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def cmd_down(args: argparse.Namespace) -> int:
    profile = _default_profile_path(args.profile)
    spec = load_stack_profile(profile)
    base = _stack_run_base(spec.name)
    session = find_latest_session_dir(base)
    if not session:
        print(f"[down] no sessions found in {base}")
        return 1
    meta = load_meta(session)
    # Terminate children (best-effort). We do not hard-kill by default.
    n = 0
    for c in meta.children.values():
        if c.pid and _pid_alive(c.pid):
            try:
                os.kill(c.pid, signal.SIGTERM)
                n += 1
            except Exception:
                pass
    print(f"[down] sent terminate to {n} processes (session {session})")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    profile = _default_profile_path(args.profile)
    spec = load_stack_profile(profile)
    base = _stack_run_base(spec.name)
    session = find_latest_session_dir(base)
    if not session:
        print(f"[logs] no sessions found in {base}")
        return 1
    log_path = session / f"{args.service}.log"
    if not log_path.exists():
        print(f"[logs] no log for {args.service} in {session}")
        return 1
    if not args.follow:
        print(log_path.read_text(encoding="utf-8", errors="replace")[-8000:])
        return 0
    # follow
    pos = 0
    try:
        while True:
            if log_path.exists():
                with log_path.open("r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                if chunk:
                    print(chunk, end="")
            time.sleep(0.25)
    except KeyboardInterrupt:
        return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    profile = _default_profile_path(args.profile)
    spec = load_stack_profile(profile, overrides=args.override, sets=args.set)
    session_dir = _stack_run_base(spec.name) / "sessions" / "PLAN"
    plan = expand_processes(spec, session_dir=session_dir)
    problems: list[str] = []

    # Check modules importable
    for svc in spec.services.values():
        if not svc.enabled:
            continue
        try:
            __import__(svc.module)
        except Exception as e:
            problems.append(f"service module import failed: {svc.module}: {e}")

    # Collect host:port tokens from argv heuristically
    hp_re = re.compile(r"^([^\s:]+):(\d{2,5})$")
    seen: dict[str, str] = {}
    for p in plan:
        for a in p.argv:
            m = hp_re.match(a)
            if not m:
                continue
            key = f"{m.group(1)}:{m.group(2)}"
            if key in seen:
                problems.append(f"port collision: {key} used by {seen[key]} and {p.name}")
            else:
                seen[key] = p.name

    if problems:
        print("[doctor] problems found:")
        for pr in problems:
            print(f"  - {pr}")
        return 2

    print(f"[doctor] OK: {spec.name} ({len(plan)} processes, {len(seen)} endpoints)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = St3DArgumentParser(prog="steuerung3d", add_help=True)
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=St3DArgumentParser)

    prof = sub.add_parser("profiles", help="List available stack profiles")
    prof.add_argument("--dir", default=None, help="Directory to scan (default: configs/stacks)")
    prof.add_argument("--paths", action="store_true", help="Print names with TOML paths")
    prof.set_defaults(_fn=cmd_profiles)

    up = sub.add_parser("up", help="Start a configured stack profile")
    up.add_argument(
        "--profile",
        required=True,
        type=_profile_arg,
        help="Profile name or path (TOML). Hint: python -m steuerung3d profiles",
    )
    up.add_argument(
        "--override",
        action="append",
        default=None,
        help="Optional override TOML (can be repeated; applied in order)",
    )
    up.add_argument(
        "--set",
        action="append",
        default=None,
        help='Inline override key=value (can be repeated), e.g. --set net.cmd_base=53001',
    )
    up.add_argument("--keep-last-sessions", type=int, default=5, help="How many sessions to keep")
    up.add_argument("--new-console", action="store_true", help="Windows: start each child in a new console window")
    up.set_defaults(_fn=cmd_up)

    plan = sub.add_parser("plan", help="Print the expanded process plan without starting it")
    plan.add_argument(
        "--profile",
        required=True,
        type=_profile_arg,
        help="Profile name or path (TOML). Hint: python -m steuerung3d profiles",
    )
    plan.add_argument("--override", action="append", default=None, help="Override TOML (repeatable)")
    plan.add_argument("--set", action="append", default=None, help="Inline override key=value (repeatable)")
    plan.set_defaults(_fn=cmd_plan)

    status = sub.add_parser("status", help="Show status for the latest session")
    status.add_argument(
        "--profile",
        required=True,
        type=_profile_arg,
        help="Profile name or path (TOML). Hint: python -m steuerung3d profiles",
    )
    status.set_defaults(_fn=cmd_status)

    down = sub.add_parser("down", help="Terminate processes from the latest session")
    down.add_argument(
        "--profile",
        required=True,
        type=_profile_arg,
        help="Profile name or path (TOML). Hint: python -m steuerung3d profiles",
    )
    down.set_defaults(_fn=cmd_down)

    logs = sub.add_parser("logs", help="Show or follow logs from the latest session")
    logs.add_argument("service", help="Service log name (e.g. core, densi-Anton, hip)")
    logs.add_argument(
        "--profile",
        required=True,
        type=_profile_arg,
        help="Profile name or path (TOML). Hint: python -m steuerung3d profiles",
    )
    logs.add_argument("--follow", action="store_true", help="Follow (tail -f)")
    logs.set_defaults(_fn=cmd_logs)

    doctor = sub.add_parser("doctor", help="Validate profile/modules/ports before starting")
    doctor.add_argument(
        "--profile",
        required=True,
        type=_profile_arg,
        help="Profile name or path (TOML). Hint: python -m steuerung3d profiles",
    )
    doctor.add_argument("--override", action="append", default=None, help="Override TOML (repeatable)")
    doctor.add_argument("--set", action="append", default=None, help="Inline override key=value (repeatable)")
    doctor.set_defaults(_fn=cmd_doctor)

    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    ns = ap.parse_args(argv)
    return int(ns._fn(ns))


if __name__ == "__main__":
    raise SystemExit(main())
