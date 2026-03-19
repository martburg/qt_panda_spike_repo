"""Stack session metadata utilities.

These are used by the unified CLI for lightweight `status`, `down`, and `logs`
operations. The goal is to stay dependency-free and work on Windows + POSIX.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, cast

from steuerung3d.core.process_liveness import pid_is_alive as _pid_is_alive

META_FILENAME = "stack_meta.json"


def _now_s() -> float:
    return float(time.time())


def _as_table(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(k): v for k, v in mapping.items()}


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


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
    children: dict[str, ChildMeta]
    stopped_at_s: Optional[float] = None

    def is_running(self) -> bool:
        if self.stopped_at_s is not None:
            return False
        # if any child is alive, consider it running
        return any(_pid_is_alive(c.pid) for c in self.children.values())


def meta_path(session_dir: Path) -> Path:
    return session_dir / META_FILENAME


def write_meta(session_dir: Path, meta: dict[str, Any]) -> None:
    p = meta_path(session_dir)
    p.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")


def load_meta(session_dir: Path) -> StackMeta:
    data_obj: object = json.loads(meta_path(session_dir).read_text(encoding="utf-8"))
    data = _as_table(data_obj)

    children: dict[str, ChildMeta] = {}
    for name, cd_obj in _as_table(data.get("children") or {}).items():
        cd = _as_table(cd_obj)
        argv_raw = cd.get("argv")
        argv_items = cast(list[object], argv_raw) if isinstance(argv_raw, list) else []
        argv = [str(x) for x in argv_items]
        returncode_obj = cd.get("returncode")
        children[name] = ChildMeta(
            name=name,
            pid=_as_int(cd.get("pid"), 0),
            argv=argv,
            log_path=str(cd.get("log_path") or ""),
            returncode=returncode_obj if isinstance(returncode_obj, int) else None,
        )

    stopped_at = data.get("stopped_at_s")
    stopped_at_s = _as_float(stopped_at) if isinstance(stopped_at, (int, float, str)) else None
    started_at = data.get("started_at_s")

    return StackMeta(
        stack_name=str(data.get("stack_name") or ""),
        session_dir=str(data.get("session_dir") or str(session_dir)),
        started_at_s=_as_float(started_at, 0.0),
        supervisor_pid=_as_int(data.get("supervisor_pid"), 0),
        profile_path=str(data.get("profile_path") or ""),
        children=children,
        stopped_at_s=stopped_at_s,
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


_STRICT_KEEP = _now_s
