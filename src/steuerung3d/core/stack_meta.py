"""Stack session metadata utilities.

These are used by the unified CLI for lightweight `status`, `down`, and `logs`
operations. The goal is to stay dependency-free and work on Windows + POSIX.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


META_FILENAME = "stack_meta.json"


def _now_s() -> float:
    return float(time.time())


def _pid_is_alive(pid: int) -> bool:
    """Best-effort check whether a process exists.

    On POSIX, os.kill(pid, 0) is the usual way. On Windows, os.kill also works
    for this check with signal 0 in modern Python.
    """

    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


@dataclass
class ChildMeta:
    name: str
    pid: int
    argv: list[str]
    log_path: str
    returncode: Optional[int] = None


@dataclass
class StackMeta:
    stack_name: str
    session_dir: str
    started_at_s: float
    supervisor_pid: int
    profile_path: str
    children: Dict[str, ChildMeta]
    stopped_at_s: Optional[float] = None

    def is_running(self) -> bool:
        if self.stopped_at_s is not None:
            return False
        # if any child is alive, consider it running
        return any(_pid_is_alive(c.pid) for c in self.children.values())


def meta_path(session_dir: Path) -> Path:
    return session_dir / META_FILENAME


def write_meta(session_dir: Path, meta: Dict[str, Any]) -> None:
    p = meta_path(session_dir)
    p.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")


def load_meta(session_dir: Path) -> StackMeta:
    data = json.loads(meta_path(session_dir).read_text(encoding="utf-8"))

    children: Dict[str, ChildMeta] = {}
    for name, cd in (data.get("children") or {}).items():
        children[name] = ChildMeta(
            name=name,
            pid=int(cd.get("pid") or 0),
            argv=list(cd.get("argv") or []),
            log_path=str(cd.get("log_path") or ""),
            returncode=cd.get("returncode"),
        )

    return StackMeta(
        stack_name=str(data.get("stack_name") or ""),
        session_dir=str(data.get("session_dir") or str(session_dir)),
        started_at_s=float(data.get("started_at_s") or 0.0),
        supervisor_pid=int(data.get("supervisor_pid") or 0),
        profile_path=str(data.get("profile_path") or ""),
        children=children,
        stopped_at_s=data.get("stopped_at_s"),
    )


def find_latest_session_dir(base_dir: Path) -> Optional[Path]:
    """Return the session dir pointed to by LATEST, if present."""

    latest = base_dir / "LATEST"
    if not latest.exists():
        return None
    try:
        target = Path(latest.read_text(encoding="utf-8").strip())
    except OSError:
        return None
    if target.exists() and target.is_dir():
        return target
    return None


def iter_session_dirs(base_dir: Path) -> Iterable[Path]:
    sessions = base_dir / "sessions"
    if not sessions.exists():
        return []
    return sorted([p for p in sessions.iterdir() if p.is_dir()], reverse=True)


def resolve_session_dir(base_dir: Path, session: Optional[str]) -> Optional[Path]:
    """Resolve a user-provided session selector.

    session can be:
      - None or "latest" => LATEST
      - an absolute/relative path
      - a leaf name under base_dir/sessions
    """

    if session is None or session == "latest":
        return find_latest_session_dir(base_dir)
    p = Path(session)
    if p.exists() and p.is_dir():
        return p
    candidate = base_dir / "sessions" / session
    if candidate.exists() and candidate.is_dir():
        return candidate
    return None
