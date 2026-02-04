"""Run a stack profile as supervised subprocesses.

This is a generalized version of the existing `setup_stack` runner:
- per-process logs in a session directory (with rollover)
- birds-eye view (log tail)
- crash tail of last N lines
- start order and simple dependency hygiene

The runtime consumes a :class:`~steuerung3d.core.stack_spec.StackSpec`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .run_dirs import make_session_dir
from .stack_render import make_context, render_argv
from .stack_spec import ProcessSpec, ServiceSpec, StackSpec
from .stack_meta import write_meta


def _now_ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _tail_lines(path: Path, n: int = 40) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-n:])


class _LogTailer:
    """Incremental tail reader for a single log file."""

    def __init__(self, path: Path):
        self.path = path
        self._pos = 0
        self.last_line: str = ""

    def poll(self) -> Optional[str]:
        if not self.path.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(self._pos)
                chunk = f.read()
                self._pos = f.tell()
        except Exception:
            return None
        if not chunk:
            return None
        # Update last non-empty line
        for line in chunk.splitlines()[::-1]:
            if line.strip():
                self.last_line = line.strip()
                break
        return self.last_line or None


@dataclass
class RunningProcess:
    spec: ProcessSpec
    popen: subprocess.Popen


def expand_processes(spec: StackSpec, *, session_dir: Path) -> List[ProcessSpec]:
    """Expand services into concrete process specs."""
    stack_ctx = {"name": spec.name}
    rig_ctx = {"axes": spec.axes}
    net_ctx = dict(spec.net)

    processes: List[ProcessSpec] = []

    def add_process(name: str, argv: List[str], svc_env: Dict[str, str]):
        log_path = session_dir / f"{name}.log"
        processes.append(ProcessSpec(name=name, argv=argv, log_path=log_path, env=svc_env))

    for svc_key, svc in spec.services.items():
        if not svc.enabled:
            continue
        if not svc.module:
            raise ValueError(f"Service '{svc_key}' has no module")

        if svc.mode == "per_axis":
            for i, axis in enumerate(spec.axes):
                ctx = make_context(stack=stack_ctx, net=net_ctx, rig=rig_ctx, axis=axis, axis_index=i)
                argv = [sys.executable, "-m", svc.module]
                argv += render_argv(_service_args_with_config(svc), ctx)
                add_process(f"{svc_key}-{axis}", argv, dict(svc.env))
        else:
            ctx = make_context(stack=stack_ctx, net=net_ctx, rig=rig_ctx, axis=None, axis_index=None)
            argv = [sys.executable, "-m", svc.module]
            argv += render_argv(_service_args_with_config(svc), ctx)
            add_process(svc_key, argv, dict(svc.env))

    return _order_processes(processes)


def _service_args_with_config(svc: ServiceSpec) -> List[object]:
    args: List[object] = list(svc.args)
    if svc.config:
        args = args + ["--config", svc.config]
    return args


def _order_processes(processes: List[ProcessSpec]) -> List[ProcessSpec]:
    """Start-order heuristic.

    Keep it stable and predictable. We prefer core before producers/consumers.
    """
    def rank(name: str) -> int:
        n = name.lower()
        if n.startswith("core"):
            return 10
        if n.startswith("densi") or n.startswith("den"):
            return 20
        if n.startswith("hip"):
            return 30
        if "input" in n:
            return 40
        if "joy" in n:
            return 50
        return 60

    return sorted(processes, key=lambda p: (rank(p.name), p.name))


class StackRuntime:
    def __init__(
        self,
        spec: StackSpec,
        *,
        run_base: Path = Path(".run"),
        keep_last_sessions: int = 5,
        new_console: bool = False,
    ):
        self.spec = spec
        self.run_base = run_base
        self.keep_last_sessions = keep_last_sessions
        self.new_console = bool(new_console)

        self.session_dir: Optional[Path] = None
        self.processes: List[RunningProcess] = []
        self.tailers: Dict[str, _LogTailer] = {}

    def start(self) -> Path:
        base = self.run_base / self.spec.name
        self.session_dir = make_session_dir(base, keep_last=self.keep_last_sessions)

        plan = expand_processes(self.spec, session_dir=self.session_dir)

        for p in plan:
            self._spawn(p)
            time.sleep(0.05)

        # Write initial metadata for status/log tooling
        self._write_meta(stopped_at_s=None)

        # tailers
        self.tailers = {rp.spec.name: _LogTailer(rp.spec.log_path) for rp in self.processes}
        return self.session_dir

    def _write_meta(self, *, stopped_at_s: float | None) -> None:
        if self.session_dir is None:
            return
        meta = {
            "stack_name": self.spec.name,
            "session_dir": str(self.session_dir),
            "profile_path": str(self.spec.profile_path) if getattr(self.spec, "profile_path", None) else "",
            "started_at_s": getattr(self, "_started_at_s", None) or time.time(),
            "stopped_at_s": stopped_at_s,
            "supervisor_pid": os.getpid(),
            "children": {
                rp.spec.name: {
                    "pid": rp.popen.pid,
                    "argv": rp.spec.argv,
                    "log_path": str(rp.spec.log_path),
                    "returncode": rp.popen.poll(),
                }
                for rp in self.processes
            },
        }
        write_meta(self.session_dir, meta)

    def _spawn(self, p: ProcessSpec):
        assert self.session_dir is not None
        p.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_f = p.log_path.open("w", encoding="utf-8")

        env = os.environ.copy()
        env.update(p.env or {})

        popen_kwargs = dict(stdout=log_f, stderr=subprocess.STDOUT, cwd=str(self.spec.base_dir), env=env)
        if self.new_console and os.name == "nt":
            # Best-effort: create a new console window for each child.
            # (Used for debugging on Windows; no-op on other platforms.)
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

        proc = subprocess.Popen(p.argv, **popen_kwargs)
        # keep file handle alive by attaching it
        proc._stack_log_fh = log_f  # type: ignore[attr-defined]
        self.processes.append(RunningProcess(spec=p, popen=proc))

    def run_forever(self) -> int:
        """Run until Ctrl+C or a child exits. Returns exit code."""
        birds_next = time.time() + 1.0
        last_birds = ""
        try:
            while True:
                # check exits
                for rp in list(self.processes):
                    rc = rp.popen.poll()
                    if rc is not None:
                        self._report_crash(rp, rc)
                        return rc if rc != 0 else 0

                now = time.time()
                if now >= birds_next:
                    birds_next = now + 1.0
                    line = self._birds_eye_line()
                    if line and line != last_birds:
                        print(line)
                        last_birds = line

                time.sleep(0.2)
        except KeyboardInterrupt:
            return 0
        finally:
            self.stop()

    def _birds_eye_line(self) -> str:
        parts: List[str] = []
        for name, t in self.tailers.items():
            t.poll()
            if t.last_line:
                parts.append(f"{name}: {t.last_line[:120]}")
        if not parts:
            return ""
        return "[birds] " + " | ".join(parts[:6])

    def _report_crash(self, rp: RunningProcess, rc: int):
        print(f"\n[stack] process exited: {rp.spec.name} pid={rp.popen.pid} rc={rc}")
        print(f"[stack] log: {rp.spec.log_path}")
        tail = _tail_lines(rp.spec.log_path, 40)
        if tail:
            print("[stack] --- last 40 lines ---")
            print(tail)
            print("[stack] ---------------------")

    def stop(self):
        # terminate children
        for rp in self.processes:
            try:
                if rp.popen.poll() is None:
                    rp.popen.terminate()
            except Exception:
                pass

        deadline = time.time() + 1.5
        for rp in self.processes:
            try:
                timeout = max(0.0, deadline - time.time())
                rp.popen.wait(timeout=timeout)
            except Exception:
                pass

        # close log handles
        for rp in self.processes:
            fh = getattr(rp.popen, "_stack_log_fh", None)
            try:
                if fh:
                    fh.close()
            except Exception:
                pass

        # final metadata snapshot
        try:
            self._write_meta(stopped_at_s=time.time())
        except Exception:
            pass

        # final metadata snapshot
        try:
            self._write_meta(stopped_at_s=time.time())
        except Exception:
            pass