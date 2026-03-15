"""CLI command implementations.

Lane 1 refactor: keep argparse plumbing separate from command bodies.
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import time
from pathlib import Path

from steuerung3d.core.stack_loader import load_stack_profile
from steuerung3d.core.stack_meta import find_latest_session_dir, load_meta
from steuerung3d.core.stack_runtime import StackRuntime, expand_processes


def discover_stack_profiles(stacks_dir: Path | None = None) -> list[str]:
    """Return available stack profile *names* (without .toml).

    Canonical location is ``configs/profiles``.
    ``configs/stacks`` remains supported for backward compatibility.
    """

    if stacks_dir is not None:
        dirs = [stacks_dir]
    else:
        dirs = [Path("configs") / "profiles", Path("configs") / "stacks"]

    names: set[str] = set()
    for d in dirs:
        if not d.exists() or not d.is_dir():
            continue
        for p in sorted(d.glob("*.toml")):
            if p.is_file():
                names.add(p.stem)
    return sorted(names)


def print_profiles(stacks_dir: Path | None = None, *, as_paths: bool = False) -> None:
    names = discover_stack_profiles(stacks_dir)
    d = stacks_dir or (Path("configs") / "profiles")
    if not names:
        print(f"[profiles] none found (looked in {d} and configs/stacks)")
        return
    print(f"[profiles] available ({len(names)}) in {d} (and configs/stacks):")
    for n in names:
        if as_paths:
            p = default_profile_path(n) if stacks_dir is None else (d / (n + ".toml"))
            print(f"- {p}")
        else:
            print(f"- {n}")


def stack_run_base(name: str) -> Path:
    return Path(".run") / name


def default_profile_path(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.suffix.lower() == ".toml" or p.exists():
        return p
    # Prefer canonical dir, fall back to legacy.
    cand = Path("configs") / "profiles" / f"{name_or_path}.toml"
    if cand.exists():
        return cand
    return Path("configs") / "stacks" / f"{name_or_path}.toml"


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def cmd_profiles(args: argparse.Namespace) -> int:
    stacks_dir = Path(args.dir) if getattr(args, "dir", None) else None
    print_profiles(stacks_dir=stacks_dir, as_paths=bool(args.paths))
    return 0


def cmd_up(args: argparse.Namespace) -> int:
    profile = default_profile_path(args.profile)
    spec = load_stack_profile(profile, overrides=args.override, sets=args.set)
    rt = StackRuntime(
        spec, keep_last_sessions=args.keep_last_sessions, new_console=bool(args.new_console)
    )
    session_dir = rt.start()
    print(f"[stack] started: {spec.name} (session {session_dir})")
    return rt.run_forever()


def cmd_plan(args: argparse.Namespace) -> int:
    profile = default_profile_path(args.profile)
    spec = load_stack_profile(profile, overrides=args.override, sets=args.set)
    session_dir = stack_run_base(spec.name) / "sessions" / "PLAN"
    plan = expand_processes(spec, session_dir=session_dir)
    for p in plan:
        print(f"- {p.name}")
        print(f"    log: {p.log_path}")
        print(f"    argv: {' '.join(p.argv)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    profile = default_profile_path(args.profile)
    spec = load_stack_profile(profile)
    base = stack_run_base(spec.name)
    session = find_latest_session_dir(base)
    if not session:
        print(f"[status] no sessions found in {base}")
        return 1
    meta = load_meta(session)
    alive = meta.is_running()
    state = "RUNNING" if alive else "STOPPED"
    print(f"[status] {meta.stack_name}: {state} (session {session})")
    for name, c in meta.children.items():
        is_up = "up" if (alive and c.pid and pid_alive(c.pid)) else "down"
        print(f"  - {name:<16} pid={c.pid:<6} {is_up} rc={c.returncode}")
    return 0 if alive else 2


def cmd_down(args: argparse.Namespace) -> int:
    profile = default_profile_path(args.profile)
    spec = load_stack_profile(profile)
    base = stack_run_base(spec.name)
    session = find_latest_session_dir(base)
    if not session:
        print(f"[down] no sessions found in {base}")
        return 1
    meta = load_meta(session)
    n = 0
    for c in meta.children.values():
        if c.pid and pid_alive(c.pid):
            try:
                os.kill(c.pid, signal.SIGTERM)
                n += 1
            except Exception:
                pass
    print(f"[down] sent terminate to {n} processes (session {session})")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    profile = default_profile_path(args.profile)
    spec = load_stack_profile(profile)
    base = stack_run_base(spec.name)
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
    profile = default_profile_path(args.profile)
    spec = load_stack_profile(profile, overrides=args.override, sets=args.set)
    session_dir = stack_run_base(spec.name) / "sessions" / "PLAN"
    plan = expand_processes(spec, session_dir=session_dir)
    problems: list[str] = []

    for svc in spec.services.values():
        if not svc.enabled:
            continue
        try:
            __import__(svc.module)
        except Exception as e:
            problems.append(f"service module import failed: {svc.module}: {e}")

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
        print("[doctor] problems:")
        for pr in problems:
            print(f"- {pr}")
        return 2

    print("[doctor] ok")
    return 0



def cmd_sup(args: argparse.Namespace) -> int:
    from steuerung3d.apps.supervisor.cli import run_supervisor

    return run_supervisor(args)
