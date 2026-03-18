"""Run a stack profile as supervised subprocesses.

This is a generalized stack supervisor/runtime used by the profile-driven boot:
- per-process logs in a session directory (with rollover)
- birds-eye view (log tail)
- crash tail of last N lines
- start order and simple dependency hygiene

The runtime consumes a :class:`~steuerung3d.core.stack_spec.StackSpec`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from steuerung3d.ui.birdseye_format import LogTailer

from .stack_runtime_boot import discover_devices, start_hips_real, start_runtime
from .stack_runtime_meta import write_runtime_meta
from .stack_runtime_processes import expand_processes as _expand_processes
from .stack_runtime_supervisor import (
    birds_eye_line,
    report_crash,
    run_forever,
    spawn_process,
    stop_runtime,
)
from .stack_spec import ProcessSpec, StackSpec
from .status import StatusCollector


@dataclass
class RunningProcess:
    spec: ProcessSpec
    popen: subprocess.Popen[bytes]


def expand_processes(spec: StackSpec, *, session_dir: Path) -> List[ProcessSpec]:
    return _order_processes(_expand_processes(spec, session_dir=session_dir))


def _order_processes(processes: List[ProcessSpec]) -> List[ProcessSpec]:
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
        self.tailers: Dict[str, LogTailer] = {}
        self.status: Optional[StatusCollector] = None

    @staticmethod
    def expand_processes_static(spec: StackSpec, *, session_dir: Path) -> List[ProcessSpec]:
        return expand_processes(spec, session_dir=session_dir)

    def start(self) -> Path:
        return start_runtime(self)

    def _discover_devices(self, *, timeout_s: float) -> List[str]:
        return discover_devices(self, timeout_s=timeout_s)

    def _start_hips_real(self) -> None:
        start_hips_real(self)

    def _write_meta(self, *, stopped_at_s: float | None) -> None:
        write_runtime_meta(self, stopped_at_s=stopped_at_s)

    def _spawn(self, p: ProcessSpec) -> None:
        spawn_process(self, p)

    def run_forever(self) -> int:
        return run_forever(self)

    def _birds_eye_line(self) -> str:
        return birds_eye_line(self)

    def _report_crash(self, rp: RunningProcess, rc: int) -> None:
        report_crash(self, rp, rc)

    def stop(self) -> None:
        stop_runtime(self)
